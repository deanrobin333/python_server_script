# TCP string lookup server

**Standardized introductory task**

* * *

## Table of contents
1. [Author details](#1-author-details)
2. [Project overview](#2-Project-overview)
3. [Code quality and standards](#3-Code-quality-and-standards)
4. [Architecture and design](#4-Architecture-and-design)
5. [Requirements](#5-Requirements)
6. [Search algorithms](#6-Search-algorithms)
7. [Configuration file](#7-Configuration-file)
8. [Running the server and client](#8-Running-the-server-and-client)
9. [SSL or TLS overview](#9-SSL-or-TLS-overview)
10. [🔐 Step by step SSL setup](#10-Step-by-step-SSL-setup)
11. [Running as a daemon (systemd)](#11-Running-as-a-daemon)
12. [Benchmarking and speed test](#12-Benchmarking-and-speed-test)
13. [Testing](#13-Testing)
14. [Limitations and notes](#14-Limitations-and-notes)
    

* * *

## 1 Author details
###### [Table of contents](#table-of-contents)

**Dean Robin Otsyeno**  
📧 *deanrobin777@gmail.com*

* * *

## 2 Project overview
###### [Table of contents](#table-of-contents)
- A short end-to-end walkthrough video of the program being used and setting up SSL can be [watched here](https://drive.google.com/file/d/1TRrCKagyFCWvnVBwOy4Rq7SrrmU_U3Gc/view?usp=drive_link)
- Project Summary
	- Project: TCP lookup service
	- Package: python_server_script
	- Application: TCP lookup service
	- Benchmark harness: benchmark_search.py
	- Module: search_engine, search, config
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
	- Production-deployable (systemd-ready)

* * *

## 3 Code quality and standards
###### [Table of contents](#table-of-contents)

- All modules and public functions are documented using **Google-style docstrings**
- Code follows **PEP8** formatting and **PEP20** design principles
- Configuration parsing is strict and validated at startup
- Errors are surfaced with clear, user-facing messages
- Tests are written using `pytest` and cover:
  - Configuration validation
  - Search correctness
  - reread_on_query behavior
  - Server/client integration
  - TLS portability

* * *

## 4 Architecture and design
###### [Table of contents](#table-of-contents)

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

## 5 Requirements
###### [Table of contents](#table-of-contents)

- Python **3.10+**
    
- Linux (tested on Ubuntu)    
- Optional:    
    - `openssl` (for SSL certificates)        
    - `nc` / `netcat` (for interactive testing)
	- `ufw` - firewall to open port 44445

- Install python dependencies (if any):
	- `pip install -r requirements.txt`


* * *

## 6 Search algorithms
###### [Table of contents](#table-of-contents)

| Algorithm | Mode | Description |
| --- | --- | --- |
| `linear_scan` | reread | Sequential scan (baseline) |
| `mmap_scan` | reread | Memory-mapped file scan |
| `grep_fx` | reread | External `grep -F -x` |
| `set_cache` | cached | O(1) hash lookup |
| `sorted_bisect` | cached | Binary search on sorted list |

- Algorithm availability is **validated at startup** based on `reread_on_query`.


* * *
## 7 Configuration file
###### [Table of contents](#table-of-contents)
- A configuration file is important. It is where settings are done.
- Create a file named `app.conf` and set the settings.
- You can use the below example.

- Example `app.conf`: - set the `linuxpath`
	```
	# Unknown keys are ignored
	foo=deanovo
	
	# Path to data file
	#linuxpath=../200k.txt
	
	# True = reread file every query
	# False = allow caching (file must be stable)
	# Use mmap_scan for large datasets when reread_on_query = True
	# Use set_cache for maximum performance when reread_on_query = False
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

## 8 Running the server and client
###### [Table of contents](#table-of-contents)

> All commands should be run from the **project root** (`python_server_script/`).

### Open specified port using firewall:
- Make sure you allow the port you will use, in this case port `44445`
- `sudo ufw allow 44445/tcp`

### Start the server

`python3 -m server --host 0.0.0.0 --port 44445 --config app.conf`

### Run a client (single query)

`python3 -m client --host 0.0.0.0 --port 44445 --config app.conf "11;0;23;16;0;18;3;0;"`

### Interactive mode (netcat)

```
nc 0.0.0.0 44445

11;0;23;16;0;18;3;0;
```

### From another computer (LAN)
- You must know the IP address of the machine running the tcp server.
- You can use `ip a` to find out the ip address
	- Example result:
		- `inet 192.168.1.33/24`
	- In this example, the server IP is: 192.168.1.33

- On client machine:

	```
	nc 192.168.1.33 444453
	0;1;28;0;7;5;0;
	```
	- Replace `192.168.1.33` with your server IP in the `nc` command above. 
- To use SSL from client machine, details explained fully below in "10 Step by step SSL setup"

* * *


## 9 SSL or TLS overview
###### [Table of contents](#table-of-contents)

### Overview

- SSL/TLS can be enabled or disabled via config
    
- Encryption and authentication are configurable separately
    
- Self-signed certificates are supported
    
- SAN-aware certificate validation supported
    

### Modes

- **Encrypted only** (`ssl_verify=False`)
    
- **Encrypted + authenticated** (`ssl_verify=True` + `ssl_cafile`)
    

### Generate a certificate (recommended) (detail procedure below)
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
## 10 Step by step SSL setup
### Generating SSL certificates
###### [Table of contents](#table-of-contents)

This server supports **TLS-encrypted connections** to protect data in transit between the client and the server. This section explains, step by step, how to generate certificates, configure the server, and connect securely from a client machine.

* * *

### Overview: what is needed

- Server side requires

	- `server.key` — the server’s **private key**
	    
	- `server.crt` — the server’s **certificate**
	    
	- `app.conf` — the server configuration file (must enable SSL)
    

- Client side requires

	- **Only a way to verify the server’s identity**
	    
	- If using a **self-signed certificate**, copy `server.crt` to the client and use it as the trust anchor via `-CAfile`
	    

> ⚠️ `app.conf` is primarily a server-side configuration file.
> The client may optionally read SSL-related settings from it when `--config` is provided.

* * *

### Step 1: prepare a directory for certificates (server)

- On the **server computer**, inside the repository root (`python_server_script`), create a directory to hold TLS files:

	- `mkdir -p certs`

- This directory will contain:

	- `certs/server.key`
	    
	- `certs/server.crt`
    

* * *

### Step 2: determine the server’s IP address

- If the client and server are on the same local network, you must use the **server’s LAN IP**, not `localhost`.

- To find the IP address on the server machine: `ip a`

- Example result:

	- `inet 192.168.1.33/24`
	
	- In this example, the server IP is:  `192.168.1.33`

- You will use this IP:

	- when generating the certificate
	    
	- when connecting from the client
    

* * *

### Step 3: generate a self-signed certificate (server)

- From the **root of the repository**, generate the certificate and key:
	```
	 openssl req -x509 -newkey rsa:2048 -keyout certs/server.key -out certs/server.crt -days 365 -nodes -subj "/CN=localhost" -addext "subjectAltName=DNS:myserver,IP:192.168.1.33"
	```

#### Important notes

- Replace `192.168.1.33` with **your actual server IP**
    
- The `subjectAltName` (SAN) is **critical**
    
    - TLS clients verify **SAN**, not just the CN
        
    - Including the IP prevents hostname mismatch errors
        
- `-nodes` ensures the private key is **not password-protected**, which is required for unattended server startup
    

- After running this command, you should have:

	```
	certs/
	├── server.crt
	└── server.key
	````

* * *

### Step 4: configure SSL in `app.conf` (server)

- On the **server computer**, open `app.conf` and update the SSL settings.

- Ensure the following values are set:

	```
	ssl_enabled = True
	
	ssl_certfile = certs/server.crt
	ssl_keyfile  = certs/server.key
	
	ssl_verify = True
	ssl_cafile = certs/server.crt
	
	```

#### What these settings mean

- `ssl_enabled=True` - Enables TLS on the server socket
    
- `ssl_certfile` / `ssl_keyfile`  - The certificate and private key used by the server
    
- `ssl_verify=True`  - Enables certificate verification logic
    
- `ssl_cafile`  - Certificate authority file (for self-signed certs, this is the same `server.crt`)
    

* * *

### Step 5: start the server with SSL enabled

- From the repository root on the **server machine**:
```
python3 -m server --host 0.0.0.0 --port 44445 --config app.conf
```

#### Notes

- `0.0.0.0` allows connections from other machines on the network
    
- The server now **expects TLS connections only**
    
- Plain `nc` (netcat) will **no longer work**
    

* * *

### Step 6: copy the certificate to the client

- On the **client computer**, copy only the certificate:
- You can manually copy it or share it via drive, or use this command from the terminal
	```
	scp user@192.168.1.33:/path/to/python_server_script/certs/server.crt ~/certs/
	```
	- replace `user` with your account's user name.

	- Or place it in any directory you prefer.

- Example client layout:

	- `~/certs/server.crt`

* * *

### Step 7: connect securely from the client

- Because `nc` does not support TLS, use `openssl s_client`.

- From the **client computer**:
	```
	openssl s_client -connect 192.168.1.33:44445 -CAfile certs/server.crt -quiet
	```

#### Flags explained

- `-connect 192.168.1.33:44445`  - Server IP and port
    
- `-CAfile certs/server.crt`  - Trust anchor for verifying the server certificate
    
- `-quiet`  - Suppresses handshake output and behaves like `nc`
    

* * *

### Step 8: query the server

- Once connected, you can paste queries directly.

- The server loads data from `200k.txt`.

- Example query: `11;0;23;16;0;18;3;0;`

- Example response:

	```
	DEBUG: ip=192.168.1.50 query='11;0;23;16;0;18;3;0;' elapsed_ms=0.214
	STRING EXISTS
	```

- The connection is:

	- Encrypted
	    
	- Persistent
	    
	- Safe to reuse for multiple queries
	    

* * *

### Common pitfalls

- ❌ Using `nc` instead of `openssl s_client`
    
- ❌ Forgetting to enable `ssl_enabled=True`
    
- ❌ Missing the server IP in `subjectAltName`
    
- ❌ Editing `app.conf` but not restarting the server
    
- ❌ Copying `app.conf` to the client (not needed)

* * *

## 11 Running as a daemon 
**systemd**
###### [Table of contents](#table-of-contents)

- Service file: `tcp-string-lookup.service`
	- In this file, the code below `# EXAMPLE` is where you set your paths

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

## 12 Benchmarking and speed test
###### [Table of contents](#table-of-contents)
- Speed test report is found here `benchmarks/speed_testing_benchmarking_report.pdf`
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
    

### CSV column meaning

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

## 13 Testing
###### [Table of contents](#table-of-contents)

- Run all tests:
	- `pytest -q`

- Test coverage includes:
	- Config parsing  
	- Protocol correctness 
	- Server/client integration
	- Algorithm consistency
	- Error handling

* * *

## 14 Limitations and notes
###### [Table of contents](#table-of-contents)

- No authentication/authorization beyond TLS
- No persistence beyond in-memory caches 
- Designed for exact full-line matches only   
- Not intended as a general-purpose database

* * *

<br></br>
<div align="right">
    <sub style="font-style: italic"> Dean Robin Otsyeno - deanrobin777@gmail.com</sub>
</div>