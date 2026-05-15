mod agent;
mod linux_desktop;
mod mac_vpn;
mod proxy_settings;
mod redaction;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            agent::agent_status,
            agent::agent_self_check,
            agent::agent_start,
            agent::agent_stop,
            agent::agent_profile_import,
            agent::agent_runtime_start,
            agent::agent_runtime_stop,
            agent::agent_uninstall_plan,
            linux_desktop::linux_desktop_package_status,
            mac_vpn::mac_vpn_prepare_underlay,
            mac_vpn::mac_vpn_restore_lan_gateway,
            mac_vpn::mac_vpn_start_root,
            mac_vpn::mac_vpn_status,
            mac_vpn::mac_vpn_stop_root,
            mac_vpn::mac_vpn_test,
            proxy_settings::system_proxy_status,
            proxy_settings::system_proxy_apply,
            proxy_settings::system_proxy_clear
        ])
        .run(tauri::generate_context!())
        .expect("error while running Proxy Gateway Test");
}
