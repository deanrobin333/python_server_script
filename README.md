# Standardized Introductory Test Task
## **Server script that binds a port and responds to connections**
---

## Table of Contents
- [Author Details](#author-details)
- [Project Description](#project-description)
- [How to run](#How-to-run)
- [Example configuration file](#Example-configuration-file)
- [SSL settings in configuration file](#SSL-settings-in-configuration-file)
- [How to run](#How-to-run)
- [Benchmarks](#Benchmarks)
- [Tasks](#tasks)
    - [0. ](#0)
    - [1. ](#1)
---
## Author Details
- *Dean Robin Otsyeno - kotsyeno@gmail.com*
---

## Project Description
###### [Table of Contents](#table-of-contents)
- A server program that:
    - runs continuously
    - listens on a network port
    - accepts connections
    - receives a query string
    - checks a file
    - returns a response
---

## How to run
###### [Table of Contents](#table-of-contents)
- “All commands should be run from the python_server_script/ directory (project root).”
- running server on terminal:
  python3 -m server --host <ip_address> --port <port_no> --config <config_file>
  example:
    `python3 -m server --host 127.0.0.1 --port 44445 --config app.conf`

- running as a client
    - search a single string
        `python3 -m client --host <ip_address> --port <port_no> --config <config_file> "<string_to_search>"`
        - example:
            `python3 -m client --host 127.0.0.1 --port 44445 --config app.conf "11;0;23;16;0;18;3;0;"`
    - run in interactive mode
        ```
        nc 127.0.0.1 44445
        11;0;23;16;0;18;3;0;
        ```
- running client from a different 
    - On primary PC start server using `python3 -m server --host 0.0.0.0 --port 44445 --config app.conf`
    - then on client computer
        ```
        nc <SERVER_IP> 44445
        3;0;1;28;0;7;5;0;
        ```
---

### Example configuration file
###### [Table of Contents](#table-of-contents)

- eg. file `app.conf`
```
# example config (unknown keys are ignored)
foo=deanovo

# PATH TO DATA FILE 
linuxpath=../200k.txt

# True = reread file every query (file may change)
# False = cache allowed (file stable)
reread_on_query=False

# Algorithms:
# reread_on_query=True  -> linear_scan, mmap_scan, grep_fx
# reread_on_query=False -> linear_scan, set_cache, sorted_bisect
search_algo=set_cache

# ENABLING SSL
# if true, must profile path to certfile and keyfile
ssl_enabled=False

ssl_certfile=certs/server.crt
ssl_keyfile=certs/server.key

# Client settings (optional)
# client SSL verification, if True must provide path to ssl_cafile
ssl_verify=False
#ssl_cafile=certs/server.crt

```
---

### SSL settings in configuration file
###### [Table of Contents](#table-of-contents)
- breakdown:
	- TLS can be enabled/disabled via `ssl_enabled`.    
	- If `ssl_enabled=True` and `ssl_verify=True`, the client verifies the server using the configured CA/certificate file (`ssl_cafile`) and validates hostname/IP via SAN.    
	- For local development, a self-signed cert is generated with SAN for both `localhost` and `127.0.0.1`.    
	- If `ssl_verify=False`, the connection is encrypted but server identity is not verified (development-only).

- Summary
    - `ssl_enabled=True/False` controls TLS on/off        
    - `ssl_verify=True/False` controls authentication strictness
    - When `ssl_verify=True`, require:        
        - `ssl_cafile` (trust anchor)            
        - and **use SAN cert** (recommended)            
    - When `ssl_verify=False`, allow insecure local testing

- Example to generate OpenSSL Certificate
    - create a certs directory `mkdir -p certs`

    - create a cert including SANs for both (better) if `ssl_verify=True` in config file
        ```    
        openssl req -x509 -newkey rsa:2048 -keyout certs/server.key -out certs/server.crt -days 365 -nodes -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
        ```
    
    - Example SAN for a LAN server at 192.168.1.20:
        ```
        openssl req -x509 -newkey rsa:2048   -keyout certs/server.key   -out certs/server.crt   -days 365 -nodes   -subj "/CN=myserver"   -addext "subjectAltName=DNS:myserver,IP:192.168.1.20"
        ```

    - create a cert without SANs for both if `ssl_verify=False` in config file
        ```        
        openssl req -x509 -newkey rsa:2048 -keyout certs/server.key -out certs/server.crt -days 365 -nodes -subj "/CN=localhost"
        ```
---
### Benchmarks
###### [Table of Contents](#table-of-contents)
- running benchmarks
    - From your project root (same place you run pytest)
    - use `--verbose` to show progress

    - quicker first run:
        `python3 -m benchmarks.benchmark_search --mode algo --sizes 10000,100000,250000 --queries 200`
        - using verbose:
            `python3 -m benchmarks.benchmark_search --mode algo --sizes 10000,100000,250000 --queries 200 --verbose`
        - for report-grade data bump the queries eg
            `python3 -m benchmarks.benchmark_search --mode algo --sizes 10000,100000,250000 --queries 1000 --verbose`
                

    - Slow:
        `python3 -m benchmarks.benchmark_search --mode both`

    - 2 directories are created in the benchmark directory: data & results
- Understanding `results_algo.csv - csv file generated by benchmark script
    - **ts**  
        - Timestamp when that benchmark row was recorded.
        
    - **algo**  
        - Which search algorithm was benchmarked (e.g., `linear_scan`, `mmap_scan`, `grep_fx`, `set_cache`, `sorted_bisect`).
        
    - **reread_on_query**  
        - The mode being simulated:
        
            - `true` = engine reads from disk each query (no caching)
                
            - `false` = engine may cache (and cached algos are only valid here)
                
    - **lines**  
        - How many lines are in the test data file (10k, 100k, 250k).
        
    - **queries**  
        - Number of queries executed in that run (you used 200).
        
    - **hits**  
        - How many of those queries were found in the file (here it’s ~102, matching your ~50% hit ratio).
        
    - **avg_ms**  
        - Mean latency **per query** in milliseconds.
        
    - **p50_ms** (median)  
        - The median query latency. Great for “typical” performance.
        
    - **p95_ms**  
        - 95th percentile latency: “worst-case-ish” for most users. Very useful.
        
    - **min_ms / max_ms**  
        - Fastest and slowest single query measured.  
        - Max is often inflated by OS scheduling, disk/cache state, or background processes.
        
    - **skipped / skip_reason**  
        - Used when a benchmark row can’t run (e.g., unsupported algo/mode). Empty here = no skips.


---
###### [Table of Contents](#table-of-contents)

<br></br>
<div align="right">
    <sub style="font-style: italic"> Dean Robin Otsyeno - kotsyeno@gmail.com</sub>
</div>