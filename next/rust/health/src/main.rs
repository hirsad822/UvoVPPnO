#[path = "lib.rs"]
mod health;

use std::{env, process};

fn run() -> Result<(), &'static str> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 6 {
        return Err("usage: pulsegrid-health LATENCY_MS LOSS_PCT REACHABLE TLS_OK SERVICE_OK");
    }
    let latency = args[1].parse::<f64>().map_err(|_| "invalid latency")?;
    let loss = args[2].parse::<f64>().map_err(|_| "invalid loss")?;
    if !latency.is_finite() || !loss.is_finite() { return Err("values must be finite"); }
    let reachable = args[3].parse::<bool>().map_err(|_| "invalid reachable flag")?;
    let tls_ok = args[4].parse::<bool>().map_err(|_| "invalid TLS flag")?;
    let service_ok = args[5].parse::<bool>().map_err(|_| "invalid service flag")?;
    println!("{}", health::score_health(latency, loss, reachable, tls_ok, service_ok));
    Ok(())
}

fn main() {
    if let Err(err) = run() { eprintln!("{}", err); process::exit(2); }
}
