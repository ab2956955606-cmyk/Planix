use std::fs::{create_dir_all, metadata, rename, OpenOptions};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tauri::{path::BaseDirectory, Manager};

const DESKTOP_LOG_MAX_BYTES: u64 = 1_000_000;
const API_PORT: &str = "8000";

// ═══════════════════════════════════════════════════════════════
// Tauri IPC proxy command — routes frontend HTTP requests through
// Rust, bypassing WebView2 mixed-content blocking entirely.
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Serialize, Deserialize)]
struct ProxyRequest {
    method: String,
    path: String,
    #[serde(default)]
    body: String,
}

#[derive(Debug, Serialize)]
struct ProxyResponse {
    status: u16,
    body: String,
}

#[tauri::command]
fn proxy_api(req: ProxyRequest) -> Result<ProxyResponse, String> {
    let url = format!("http://127.0.0.1:{}{}", API_PORT, req.path);
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(45))
        .build()
        .map_err(|e| format!("failed to create HTTP client: {e}"))?;

    let resp = match req.method.to_uppercase().as_str() {
        "GET" => client.get(&url),
        "POST" => {
            let mut builder = client.post(&url);
            if !req.body.is_empty() {
                builder = builder.header("Content-Type", "application/json");
                builder = builder.body(req.body);
            }
            builder
        }
        "PUT" => {
            let mut builder = client.put(&url);
            if !req.body.is_empty() {
                builder = builder.header("Content-Type", "application/json");
                builder = builder.body(req.body);
            }
            builder
        }
        "PATCH" => {
            let mut builder = client.patch(&url);
            if !req.body.is_empty() {
                builder = builder.header("Content-Type", "application/json");
                builder = builder.body(req.body);
            }
            builder
        }
        "DELETE" => client.delete(&url),
        other => return Err(format!("unsupported method: {other}")),
    };

    let resp = resp.send().map_err(|e| format!("proxy request failed: {e}"))?;
    let status = resp.status().as_u16();
    let body = resp.text().map_err(|e| format!("reading response body: {e}"))?;

    Ok(ProxyResponse { status, body })
}

// ═══════════════════════════════════════════════════════════════
// Sidecar management (unchanged logic, extracted here)
// ═══════════════════════════════════════════════════════════════

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
    use windows_sys::Win32::Foundation::{GetLastError, ERROR_ALREADY_EXISTS};
    use windows_sys::Win32::System::Threading::CreateMutexW;

    let name: Vec<u16> = OsStr::new("MyNotesAI-Desktop-Instance")
        .encode_wide()
        .chain(once(0))
        .collect();

    let handle = unsafe { CreateMutexW(std::ptr::null_mut(), 0, name.as_ptr()) };
    if handle.is_null() {
        let msg = format!("CreateMutexW failed: last_error={}", unsafe { GetLastError() });
        write_log(log, &msg);
        return Err(msg.into());
    }

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
    if metadata(path)
        .map(|meta| meta.len() > DESKTOP_LOG_MAX_BYTES)
        .unwrap_or(false)
    {
        let rotated = path.with_extension("log.old");
        let _ = rename(path, rotated);
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

#[derive(Debug)]
struct HealthInfo {
    app: Option<String>,
    pid: Option<u32>,
    version: Option<String>,
    body: String,
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

    let body = match response.find('{') {
        Some(pos) => response[pos..].to_string(),
        None => return Err("no JSON body in health response".to_string()),
    };

    let is_mynotes =
        body.contains(r#""app":"mynotes-api""#) || body.contains(r#""app": "mynotes-api""#);
    if !is_mynotes || !(body.contains(r#""status":"ok""#) || body.contains(r#""status": "ok""#)) {
        return Err(format!("port {port} is not serving MyNotes API: {body}"));
    }

    let pid = extract_json_u32(&body, "pid");
    let version = extract_json_str(&body, "version");
    Ok(HealthInfo {
        app: Some("mynotes-api".to_string()),
        pid,
        version,
        body,
    })
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
                             app={:?} pid={:?} version={:?} body={}",
                            info.app, info.pid, info.version, info.body
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
            let mut conflict_reported = false;
            loop {
                match pipe.read(&mut buffer) {
                    Ok(0) => return,
                    Ok(size) => {
                        let text = String::from_utf8_lossy(&buffer[..size]);
                        write_log(&log_path, format!("mynotes-api {label}: {}", text.trim()));
                        let lower = text.to_lowercase();
                        let port_conflict = label == "stderr"
                            && (lower.contains("10048")
                                || lower.contains("winerror 10048")
                                || lower.contains("address already in use")
                                || lower.contains("only one usage")
                                || lower.contains("通常每个套接字地址"));
                        if port_conflict && !conflict_reported {
                            conflict_reported = true;
                            write_log(&log_path, "port 8000 is already in use");
                            show_error(
                                "MyNotes AI",
                                &format!(
                                    "MyNotes AI 后端启动失败：8000 端口已被占用。\n请关闭占用 8000 端口的程序后重试。\n\n日志：{}",
                                    log_path.display()
                                ),
                            );
                        }
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

// ═══════════════════════════════════════════════════════════════
// Main entry point
// ═══════════════════════════════════════════════════════════════

fn main() {
    let startup_log_path = log_path();
    write_log(&startup_log_path, "app start time");

    if let Err(e) = ensure_single_instance(&startup_log_path) {
        write_log(
            &startup_log_path,
            format!("single-instance check failed: {e}"),
        );
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![proxy_api])
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

            let already_running = match get_api_health(&port) {
                Ok(info) => {
                    write_log(
                        &log_path,
                        format!(
                            "preflight /api/health result: success — \
                             app={:?} pid={:?} version={:?} body={}",
                            info.app, info.pid, info.version, info.body
                        ),
                    );
                    true
                }
                Err(err) => {
                    let is_port_closed = err.contains("Connection refused")
                        || err.contains("connection refused")
                        || err.contains("10061")
                        || err.contains("actively refused")
                        || err.contains("No connection could be made");
                    if !is_port_closed {
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
                        format!("preflight /api/health result: not reachable ({err})"),
                    );
                    false
                }
            };

            if already_running {
                write_log(
                    &log_path,
                    "existing MyNotes API detected, skip spawning sidecar",
                );
                app.manage(ApiSidecar(Mutex::new(None)));
                return Ok(());
            }

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

            let mut sidecar = Command::new(&sidecar_path);
            sidecar
                .env("MYNOTES_ENV", "desktop")
                .env("MYNOTES_API_PORT", port.clone())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped());

            if let Ok(key) = std::env::var("DEEPSEEK_API_KEY") {
                if !key.is_empty() {
                    sidecar.env("DEEPSEEK_API_KEY", key);
                    write_log(&log_path, "forwarded DEEPSEEK_API_KEY to sidecar");
                }
            }
            if let Ok(key) = std::env::var("AI_API_KEY") {
                if !key.is_empty() {
                    sidecar.env("AI_API_KEY", key);
                    write_log(&log_path, "forwarded AI_API_KEY to sidecar");
                }
            }
            if let Ok(use_real) = std::env::var("USE_REAL_LLM") {
                sidecar.env("USE_REAL_LLM", use_real);
                write_log(&log_path, "forwarded USE_REAL_LLM to sidecar");
            }

            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                sidecar.creation_flags(0x08000000);
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
