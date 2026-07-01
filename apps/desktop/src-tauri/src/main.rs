use std::sync::Mutex;

use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

struct ApiSidecar(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if std::env::var("MYNOTES_SKIP_SIDECAR").is_ok() {
                return Ok(());
            }

            let port = std::env::var("MYNOTES_API_PORT").unwrap_or_else(|_| "8000".to_string());
            let sidecar = app
                .shell()
                .sidecar("mynotes-api")?
                .env("MYNOTES_ENV", "desktop")
                .env("MYNOTES_API_PORT", port);

            let (mut receiver, child) = sidecar.spawn()?;
            app.manage(ApiSidecar(Mutex::new(Some(child))));

            tauri::async_runtime::spawn(async move {
                while let Some(event) = receiver.recv().await {
                    println!("mynotes-api sidecar: {event:?}");
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running MyNotes AI desktop");
}
