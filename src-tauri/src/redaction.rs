pub fn redact(input: &str) -> String {
    let mut output = String::with_capacity(input.len());
    for line in input.lines() {
        let lower = line.to_ascii_lowercase();
        let proxy_uri = ["ss", "vmess", "trojan"]
            .iter()
            .any(|scheme| lower.contains(&format!("{scheme}://")));
        if lower.contains("password")
            || lower.contains("passwd")
            || lower.contains("api_key")
            || lower.contains("apikey")
            || lower.contains("credential")
            || lower.contains("auth")
            || lower.contains("\"server\"")
            || lower.contains("server:")
            || lower.contains("server=")
            || lower.contains("server_port")
            || proxy_uri
        {
            output.push_str("[redacted]\n");
        } else {
            output.push_str(line);
            output.push('\n');
        }
    }
    output
}
