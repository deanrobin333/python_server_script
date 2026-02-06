# TCP String Lookup Server

**Standardized Introductory Test Task**

* * *

## Table of Contents
1. [Author Details](#author-details)
2. [Project Overview](#Project-Overview)
3. [Architecture and Design](#Architecture-and-Design)
4. [Requirements](#Requirements)
5. [Running the Server and Client](#Running-the-Server-and-Client)
6. [Configuration File](#Configuration-File)
7. [Search Algorithms](#Search-Algorithms)
8. [SSL or TLS Support](#SSL-or-TLS-Support)
9. [Running as a Daemon (systemd)](#Running-as-a-Daemon)
10. [Benchmarking](#Benchmarking)
11. [Testing](#Testing)
12. [Limitations and Notes](#Limitations-and-Notes)
    

* * *

## Author Details
###### [Table of Contents](#table-of-contents)

**Dean Robin Otsyeno**  
📧 *kotsyeno@gmail.com*

* * *

## Project Overview
###### [Table of Contents](#table-of-contents)

- This project implements a **high-performance TCP server** that:

	- Runs continuously
	    
	- Binds to a configurable network port
	    
	- Accepts multiple client connections concurrently
	    
	- Receives query strings
	    
	- Performs exact full-line lookups in a data file
	    
	- Returns structured responses
	    
	- Supports multiple search algorithms
	    
	- Supports optional SSL/TLS encryption
	    
	- Includes benchmarking and automated tests
    

- The server is designed to be:

	- Configurable
	    
	- Secure
	    
	- Performant
	    
	- Production-deployable (systemd-ready)
    

* * *

## Architecture and Design
###### [Table of Contents](#table-of-contents)

**Core components:**

- `server.py` — TCP server implementation
    
- `client.py` — CLI client
    
- `search_engine.py` — algorithm dispatch + caching
    
- `search.py` — individual search implementations
    
- `config.py` — strict configuration parsing & validation
    
- `benchmarks/` — performance benchmarking harness
    
- `tests/` — pytest-based test suite
    

**Concurrency model:**

- One thread per client connection
    
- Persistent connections supported (multiple queries per connection)
    
- Graceful shutdown handling
    

* * *

## Requirements
###### [Table of Contents](#table-of-contents)

- Python **3.10+**
    
- Linux (tested on Ubuntu)
    
- Optional:
    
    - `openssl` (for SSL certificates)
        
    - `nc` / `netcat` (for interactive testing)
        

- Install Python dependencies (if any):

	- `pip install -r requirements.txt`

* * *

## Running the Server and Client
###### [Table of Contents](#table-of-contents)

> All commands should be run from the **project root** (`python_server_script/`).

### Start the server

`python3 -m server --host 127.0.0.1 --port 44445 --config app.conf`

### Run a client (single query)

`python3 -m client --host 127.0.0.1 --port 44445 --config app.conf "11;0;23;16;0;18;3;0;"`

### Interactive mode (netcat)

`nc 127.0.0.1 4444511;0;23;16;0;18;3;0;`

### From another computer (LAN)

- On server machine:

	- `python3 -m server --host 0.0.0.0 --port 44445 --config app.conf`

- Open firewall:

	- `sudo ufw allow 44445/tcp`

- On client machine:

	- `nc <SERVER_IP> 444453;0;1;28;0;7;5;0;`

* * *

## Configuration File
###### [Table of Contents](#table-of-contents)

- Example `app.conf`: - set the `linxpath`
	```
	# Unknown keys are ignored
	foo=deanovo
	
	# Path to data file
	linuxpath=../200k.txt
	
	# True = reread file every query
	# False = allow caching (file must be stable)
	reread_on_query=False
	
	# Algorithms:
	# reread_on_query=True  -> linear_scan, mmap_scan, grep_fx
	# reread_on_query=False -> linear_scan, set_cache, sorted_bisect
	search_algo=set_cache
	
	# SSL/TLS
	ssl_enabled=False
	# ssl_certfile=certs/server.crt
	# ssl_keyfile=certs/server.key
	
	# Client verification options
	ssl_verify=False
	# ssl_cafile=certs/server.crt
	
	```

* * *

## Search Algorithms
###### [Table of Contents](#table-of-contents)

| Algorithm | Mode | Description |
| --- | --- | --- |
| `linear_scan` | reread | Sequential scan (baseline) |
| `mmap_scan` | reread | Memory-mapped file scan |
| `grep_fx` | reread | External `grep -F -x` |
| `set_cache` | cached | O(1) hash lookup |
| `sorted_bisect` | cached | Binary search on sorted list |

- Algorithm availability is **validated at startup** based on `reread_on_query`.

* * *

## SSL or TLS Support
###### [Table of Contents](#table-of-contents)

### Overview

- SSL/TLS can be enabled or disabled via config
    
- Encryption and authentication are configurable separately
    
- Self-signed certificates are supported
    
- SAN-aware certificate validation supported
    

### Modes

- **Encrypted only** (`ssl_verify=False`)
    
- **Encrypted + authenticated** (`ssl_verify=True` + `ssl_cafile`)
    

### Generate a certificate (recommended)
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

### Summary

- `ssl_enabled=True` → TLS enabled
    
- `ssl_verify=True` → certificate verification enforced
    
- `ssl_verify=False` → encryption only (dev/testing)
    

* * *

## Running as a Daemon 
**systemd**
###### [Table of Contents](#table-of-contents)

- Service file: `tcp-string-lookup.service`

- Key steps:

	```
	# Create a dedicated service user (recommended)
	sudo useradd --system --no-create-home --shell /usr/sbin/nologin tcpstring
	
	sudo mkdir -p /opt/python_server_script
	sudo rsync -a ./python_server_script/ /opt/python_server_script/
	sudo chown -R tcpstring:tcpstring /opt/python_server_script
	```

- Install service:

	```
	sudo cp tcp-string-lookup.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable tcp-string-lookup
	sudo systemctl start tcp-string-lookup
	
	````

- Check status:

	`sudo systemctl status tcp-string-lookup --no-pager`

- Logs:

	`sudo journalctl -u tcp-string-lookup -f`

* * *

## Benchmarking
###### [Table of Contents](#table-of-contents)

- Run benchmarks:
    - quicker first run:
	  - `python3 -m benchmarks.benchmark_search --mode algo --sizes 10000,100000,250000 --queries 1000 --verbose`	   
    - run for 200 queries
        - `python3 -m benchmarks.benchmark_search --mode algo --sizes 10000,100000,250000 --queries 200`
                
    - Slow:
        - `python3 -m benchmarks.benchmark_search --mode both`



- Generated outputs:

	- `benchmarks/data/`
	    
	- `benchmarks/results/results_algo.csv`
    

### CSV Column Meaning

| Column | Meaning |
| --- | --- |
| `ts` | Timestamp of run |
| `algo` | Algorithm used |
| `reread_on_query` | Disk vs cached mode |
| `lines` | Dataset size |
| `queries` | Number of queries |
| `hits` | Successful lookups |
| `avg_ms` | Average latency |
| `p50_ms` | Median latency |
| `p95_ms` | Tail latency |
| `min_ms` | Fastest query |
| `max_ms` | Slowest query |

* * *

## Testing
###### [Table of Contents](#table-of-contents)

- Run all tests:

	- `pytest -q`

- Test coverage includes:

	- Config parsing
	    
	- Protocol correctness
	    
	- Server/client integration
	    
	- Algorithm consistency
	    
	- Error handling
    

* * *

## Limitations and Notes
###### [Table of Contents](#table-of-contents)

- No authentication/authorization beyond TLS
    
- No persistence beyond in-memory caches
    
- Designed for exact full-line matches only
    
- Not intended as a general-purpose database
    

* * *

<br></br>
<div align="right">
    <sub style="font-style: italic"> Dean Robin Otsyeno - kotsyeno@gmail.com</sub>
</div>