# Standardized Introductory Test Task
## **Server script that binds a port and responds to connections**
---

## Table of Contents
- [Author Details](#author-details)
- [Project Description](#project-description)
- [Tasks](#tasks)
    - [0. ](#0)
    - [1. ](#1)
---
## Author Details
- *Dean Robin Otsyeno - kotsyeno@gmail.com*
---

## Project Description
- A server program that:
    - runs continuously
    - listens on a network port
    - accepts connections
    - receives a query string
    - checks a file
    - returns a response
---

## How to run
- “All commands should be run from the python_server_script/ directory (project root).”
- running server on terminal:
  python3 -m server --host <ip_address> --port <port_no> --config <config_file>
  example:
    python3 -m server --host 127.0.0.1 --port 44445 --config app.conf

- running benchmarks
    - From your project root (same place you run pytest):
        `python3 -m benchmarks.benchmark_search --mode both`
        show progress
        `python3 -m benchmarks.benchmark_search --mode both --verbose`

    - Or quicker first run:
        `python3 -m benchmarks.benchmark_search --mode algo --sizes 10000,100000,250000 --queries 200`

    - 2 directories are created in the benchmark directory: data & results


---
## Tasks
#### 0
###### [Table of Contents](#table-of-contents)
### [0. ](./)

---
#### 1
###### [Table of Contents](#table-of-contents)
### [1. ](./)

---


<br></br>
<div align="right">
    <sub style="font-style: italic"> Dean Robin Otsyeno - kotsyeno@gmail.com</sub>
</div>