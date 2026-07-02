use std::fs::{create_dir_all, OpenOptions};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use tauri::{path::BaseDirectory, Manager};

/// Wraps the optional sidecar child process.
/// Drop kills the child only if WE spawned it.
struct ApiSidecar(Mutex<Option<Child>>);

impl Drop for ApiSidecar {
    fn drop(&mut self) {
        if let Ok(mut child) = self.0.lock() {
            if let Some(mut child) = child.take() {
                let _ = child.kill();
            }
        }
    }
}

// ── Windows named mutex for single-instance  ────────────────────
#[cfg(windows)]
fn ensure_single_instance(log: &PathBuf) -> Result<(), Box<dyn std::error::Error>> {
    use std::ffi::OsStr;
    use std::iter::once;
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::System::Threading::{
        CreateMutexW, GetLastError, ERROR_ALREADY_EXISTS,
    };

    let name: Vec<u16> = OsStr::new("MyNotesAI-Desktop-Instance")
        .encode_wide()
        .chain(once(0))
        .collect();

    // SAFETY: Win32 API call with valid null-terminated wide string.
    let handle = unsafe { CreateMutexW(std::ptr::null_mut(), 0, name.as_ptr()) };
    if handle.is_null() {
        let msg = format!("CreateMutexW failed: last_error={}", unsafe { GetLastError() });
        write_log(log, &msg);
        return Err(msg.into());
    }

    // ERROR_ALREADY_EXISTS means another instance holds the mutex.
    if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
        write_log(log, "another instance detected via named mutex, exiting");
        return Err("Another instance is already running.".into());
    }

    write_log(log, "single-instance mutex acquired");
    Ok(())
}

#[cfg(not(windows))]
fn ensure_single_instance(_log: &PathBuf) -> Result<(), Box<dyn std::error::Error>> {
    Ok(())
}

// ── Logging helpers  ────────────────────────────────────────────

fn log_path() -> PathBuf {
    if let Ok(appdata) = std::env::var("APPDATA") {
        return PathBuf::from(appdata)
            .join("MyNotes AI")
            .join("logs")
            .join("desktop.log");
    }

    std::env::temp_dir()
        .join("MyNotes AI")
        .join("logs")
        .join("desktop.log")
}

fn timestamp() -> String {
    match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(duration) => format!("{}", duration.as_secs()),
        Err(_) => "unknown-time".to_string(),
    }
}

fn write_log(path: &PathBuf, message: impl AsRef<str>) {
    if let Some(parent) = path.parent() {
        let _ = create_dir_all(parent);
    }

    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "[{}] {}", timestamp(), message.as_ref());
    }
}

// ── Windows error dialog  ───────────────────────────────────────

#[cfg(windows)]
fn show_error(title: &str, message: &str) {
    use std::iter::once;
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK};

    let title_wide: Vec<u16> = std::ffi::OsStr::new(title)
        .encode_wide()
        .chain(once(0))
        .collect();
    let message_wide: Vec<u16> = std::ffi::OsStr::new(message)
        .encode_wide()
        .chain(once(0))
        .collect();

    unsafe {
        MessageBoxW(
            std::ptr::null_mut(),
            message_wide.as_ptr(),
            title_wide.as_ptr(),
            MB_OK | MB_ICONERROR,
        );
    }
}

#[cfg(not(windows))]
fn show_error(title: &str, message: &str) {
    eprintln!("{title}: {message}");
}

// ── Raw TCP-based health check  ─────────────────────────────────
//
// We use raw TCP (not reqwest) to keep the Tauri binary lightweight.
// The response body is parsed minimally via the JSON fields we need.

#[derive(Debug)]
struct HealthInfo {
    app: Option<String>,
    pid: Option<u32>,
    version: Option<String>,
}

fn get_api_health(port: &str) -> Result<HealthInfo, String> {
    let address = format!("127.0.0.1:{port}");
    let mut stream = TcpStream::connect(address.as_str()).map_err(|err| err.to_string())?;
    stream
        .set_read_timeout(Some(Duration::from_secs(3)))
        .map_err(|err| err.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_secs(3)))
        .map_err(|err| err.to_string())?;

    let request =
        format!("GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n");
    stream
        .write_all(request.as_bytes())
        .map_err(|err| err.to_string())?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|err| err.to_string())?;

    // Parse JSON body after headers (look for '{')
    let body = match response.find('{') {
        Some(pos) => &response[pos..],
        None => return Err("no JSON body in health response".to_string()),
    };

    // Look for "app":"mynotes-api" or "app": "mynotes-api"
    let is_mynotes = body.contains(r#""app":"mynotes-api""#)
        || body.contains(r#""app": "mynotes-api""#);

    if !is_mynotes || !(body.contains(r#""status":"ok""#) || body.contains(r#""status": "ok""#)) {
        return Err(format!(
            "port {port} is not serving MyNotes API: {body}"
        ));
    }

    // Extract pid and version by simple scan (no JSON parser dependency)
    let pid = extract_json_u32(body, "pid");
    let version = extract_json_str(body, "version");
    let app = Some("mynotes-api".to_string());

    Ok(HealthInfo { app, pid, version })
}

fn extract_json_str(body: &str, key: &str) -> Option<String> {
    let pattern_a = format!(r#""{}":""#, key);
    let pattern_b = format!(r#""{}": ""#, key);
    for pattern in &[pattern_a, pattern_b] {
        if let Some(start) = body.find(pattern.as_str()) {
            let rest = &body[start + pattern.len()..];
            if let Some(end) = rest.find('"') {
                return Some(rest[..end].to_string());
            }
        }
    }
    None
}

fn extract_json_u32(body: &str, key: &str) -> Option<u32> {
    let pattern_a = format!(r#""{}":"#, key);
    let pattern_b = format!(r#""{}": "#, key);
    for pattern in &[pattern_a, pattern_b] {
        if let Some(start) = body.find(pattern.as_str()) {
            let rest = &body[start + pattern.len()..];
            let digits: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
            if !digits.is_empty() {
                return digits.parse().ok();
            }
        }
    }
    None
}

// ── Sidecar health polling  ─────────────────────────────────────

fn poll_api_health(port: String, log_path: PathBuf) {
    std::thread::spawn(move || {
        for attempt in 1..=30 {
            match get_api_health(&port) {
                Ok(info) => {
                    write_log(
                        &log_path,
                        format!(
                            "/api/health check result: success on attempt {attempt}: \
                             app={:?} pid={:?} version={:?}",
                            info.app, info.pid, info.version
                        ),
                    );
                    return;
                }
                Err(err) => {
                    write_log(
                        &log_path,
                        format!("/api/health check result: attempt {attempt} failed: {err}"),
                    );
                    std::thread::sleep(Duration::from_secs(1));
                }
            }
        }

        let message = format!(
            "MyNotes AI 后端启动失败。可能原因：8000 端口被占用，或安装包不完整。请重启电脑后重试，或查看日志：{}",
            log_path.display()
        );
        write_log(&log_path, "sidecar health check failed after 30 seconds");
        show_error("MyNotes AI", &message);
    });
}

// ── Sidecar output piping  ──────────────────────────────────────

fn pipe_sidecar_output(
    log_path: PathBuf,
    label: &'static str,
    pipe: Option<impl Read + Send + 'static>,
) {
    if let Some(mut pipe) = pipe {
        std::thread::spawn(move || {
            let mut buffer = [0_u8; 1024];
            loop {
                match pipe.read(&mut buffer) {
                    Ok(0) => return,
                    Ok(size) => {
                        let text = String::from_utf8_lossy(&buffer[..size]);
                        write_log(&log_path, format!("mynotes-api {label}: {}", text.trim()));
                    }
                    Err(err) => {
                        write_log(&log_path, format!("mynotes-api {label} read error: {err}"));
                        return;
                    }
                }
            }
        });
    }
}

// ── Main  ───────────────────────────────────────────────────────

fn main() {
    let startup_log_path = log_path();
    write_log(&startup_log_path, "app start time");

    // Single-instance check (Windows named mutex)
    if let Err(e) = ensure_single_instance(&startup_log_path) {
        write_log(
            &startup_log_path,
            format!("single-instance check failed: {e}"),
        );
        // Don't block — allow second window; the preflight health check
        // will prevent a second sidecar.
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let log_path = log_path();
            write_log(&log_path, "setup started");

            match app.path().resource_dir() {
                Ok(resource_dir) => {
                    write_log(
                        &log_path,
                        format!("frontendDist/resource path: {}", resource_dir.display()),
                    );
                }
                Err(err) => {
                    let message = format!(
                        "MyNotes AI 前端资源加载失败。安装包可能不完整，缺少 index.html。请重新安装最新 MSI。\n\n日志：{}",
                        log_path.display()
                    );
                    write_log(&log_path, format!("frontendDist path error: {err}"));
                    show_error("MyNotes AI", &message);
                    return Err(Box::new(err));
                }
            }

            match app.path().resolve("resources/index.html", BaseDirectory::Resource) {
                Ok(index_path) => {
                    write_log(
                        &log_path,
                        format!(
                            "index.html existence check result: {} ({})",
                            index_path.exists(),
                            index_path.display()
                        ),
                    );
                }
                Err(err) => {
                    write_log(&log_path, format!("index.html resolve check failed: {err}"));
                }
            }

            if std::env::var("MYNOTES_SKIP_SIDECAR").is_ok() {
                write_log(
                    &log_path,
                    "MYNOTES_SKIP_SIDECAR is set; sidecar startup skipped for development",
                );
                return Ok(());
            }

            let port = std::env::var("MYNOTES_API_PORT").unwrap_or_else(|_| "8000".to_string());
            write_log(&log_path, format!("MYNOTES_API_PORT={port}"));

            // ── Preflight: check if a MyNotes API is already running ──
            let already_running = match get_api_health(&port) {
                Ok(info) => {
                    write_log(
                        &log_path,
                        format!(
                            "preflight /api/health result: success — \
                             app={:?} pid={:?} version={:?}",
                            info.app, info.pid, info.version
                        ),
                    );
                    true
                }
                Err(err) => {
                    // Distinguish port-open-but-not-our-API vs port-closed.
                    // get_api_health returns Err when:
                    //   - TCP connect failed (port closed) → "Connection refused"
                    //   - TCP connected but response isn't MyNotes API → body in err
                    //   - TCP connected but no JSON body → "no JSON body"
                    let is_port_closed = err.contains("Connection refused")
                        || err.contains("10061")
                        || err.contains("actively refused");
                    let is_other_service = !is_port_closed;

                    if is_other_service {
                        let msg = format!(
                            "MyNotes AI 后端启动失败：8000 端口已被其他程序占用。\
                             请关闭占用 8000 端口的程序后重试。\n\n诊断：{err}"
                        );
                        write_log(
                            &log_path,
                            format!("preflight health check: PORT CONFLICT — {err}"),
                        );
                        show_error("MyNotes AI", &msg);
                        return Err(
                            std::io::Error::new(std::io::ErrorKind::AddrInUse, msg).into()
                        );
                    }
                    write_log(
                        &log_path,
                        format!(
                            "preflight /api/health result: not reachable ({err})"
                        ),
                    );
                    false
                }
            };

            if already_running {
                write_log(
                    &log_path,
                    "existing MyNotes API detected on 127.0.0.1:8000, skip spawning sidecar",
                );
                // No sidecar child to manage.
                app.manage(ApiSidecar(Mutex::new(None)));
                return Ok(());
            }

            // ── Ensure sidecar binary exists ──
            let sidecar_path = match app
                .path()
                .resolve("resources/binaries/mynotes-api.exe", BaseDirectory::Resource)
            {
                Ok(path) => {
                    write_log(
                        &log_path,
                        format!(
                            "sidecar expected path: {} exists={}",
                            path.display(),
                            path.exists()
                        ),
                    );
                    path
                }
                Err(err) => {
                    let message = format!(
                        "MyNotes AI 后端启动失败。安装包不完整，缺少 resources\\binaries\\mynotes-api.exe。\
                         请重新安装最新 MSI，或查看日志：{}",
                        log_path.display()
                    );
                    write_log(&log_path, format!("sidecar expected path resolve failed: {err}"));
                    show_error("MyNotes AI", &message);
                    return Err(Box::new(err));
                }
            };

            if !sidecar_path.exists() {
                let message = format!(
                    "MyNotes AI 后端启动失败。安装包不完整，缺少 resources\\binaries\\mynotes-api.exe。\
                     请重新安装最新 MSI，或查看日志：{}",
                    log_path.display()
                );
                write_log(
                    &log_path,
                    format!("sidecar missing at {}", sidecar_path.display()),
                );
                show_error("MyNotes AI", &message);
                return Err(std::io::Error::new(std::io::ErrorKind::NotFound, message).into());
            }

            // ── Spawn sidecar ──
            let mut sidecar = Command::new(&sidecar_path);
            sidecar
                .env("MYNOTES_ENV", "desktop")
                .env("MYNOTES_API_PORT", port.clone())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped());

            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                sidecar.creation_flags(0x08000000); // CREATE_NO_WINDOW
            }

            let mut child = match sidecar.spawn() {
                Ok(result) => result,
                Err(err) => {
                    let message = format!(
                        "MyNotes AI 后端启动失败。可能原因：8000 端口被占用，或安装包不完整。\
                         请重启电脑后重试，或查看日志：{}",
                        log_path.display()
                    );
                    write_log(&log_path, format!("sidecar start failure: {err}"));
                    show_error("MyNotes AI", &message);
                    return Err(Box::new(err));
                }
            };

            write_log(&log_path, "sidecar start success");
            pipe_sidecar_output(log_path.clone(), "stdout", child.stdout.take());
            pipe_sidecar_output(log_path.clone(), "stderr", child.stderr.take());
            app.manage(ApiSidecar(Mutex::new(Some(child))));

            // ── Poll until healthy ──
            poll_api_health(port, log_path);

            Ok(())
        })
        .run(tauri::generate_context!())
        .unwrap_or_else(|err| {
            let message = format!(
                "MyNotes AI 启动失败。请查看日志：{}\n\n错误：{}",
                startup_log_path.display(),
                err
            );
            write_log(&startup_log_path, format!("app runtime error: {err}"));
            show_error("MyNotes AI", &message);
        });
}
