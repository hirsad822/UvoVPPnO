//! Health scoring implementation for the future Rust diagnostic worker.

/// Calculate the weighted health score used by PulseGrid.
pub fn score_health(latency_ms: f64, loss_pct: f64, reachable: bool, tls_ok: bool, service_ok: bool) -> u8 {
    if !reachable { return 0; }
    let latency = if latency_ms <= 0.0 { 0 } else if latency_ms < 50.0 { 30 }
        else if latency_ms < 100.0 { 24 } else if latency_ms < 150.0 { 18 }
        else if latency_ms < 250.0 { 10 } else { 4 };
    let loss = if loss_pct <= 0.0 { 25 } else if loss_pct < 2.0 { 20 }
        else if loss_pct < 5.0 { 14 } else if loss_pct < 10.0 { 8 } else { 3 };
    latency + loss + 20 + (if tls_ok { 15 } else { 0 }) + (if service_ok { 10 } else { 0 })
}

pub fn verdict(score: u8) -> &'static str {
    if score >= 80 { "healthy" } else if score >= 50 { "degraded" } else { "unhealthy" }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn unreachable_is_zero() { assert_eq!(score_health(10.0, 0.0, false, true, true), 0); }
    #[test] fn ideal_score() { assert_eq!(score_health(10.0, 0.0, true, true, true), 100); }
    #[test] fn degrades() { assert!(score_health(500.0, 20.0, true, true, true) < score_health(10.0, 0.0, true, true, true)); }
    #[test] fn thresholds() { assert_eq!(verdict(80), "healthy"); assert_eq!(verdict(50), "degraded"); assert_eq!(verdict(49), "unhealthy"); }
}
