# PyFlexiProxy

**PyFlexiProxy** is a flexible, high-performance proxy server written in Python. It supports both forward and reverse proxy modes and is designed for modern Linux systems, leveraging advanced I/O features for efficient concurrent request handling.

---

## Features

- **Master-Worker Architecture:**  
  A master process manages configuration and socket setup, while multiple worker processes handle client connections.

- **Linux EPOLL with EPOLLEXCLUSIVE:**  
  Uses the Linux-specific `epoll` interface with `EPOLLEXCLUSIVE` for scalable, efficient management of thousands of concurrent connections.  
  **Note:** Requires Linux kernel version 4.5 or higher.

- **Flexible Configuration:**  
  All proxy settings are defined in a YAML file (`config.yaml`). Easily configure ports, upstream servers, headers, and routing paths.

- **Custom Headers & Routing:**  
  Add custom headers and define path-based routing to multiple upstream servers.

- **Forward & Reverse Proxy:**  
  Designed to be configurable as both a forward and reverse proxy.

---

## Example Configuration

See [`config.example.yaml`](src/config.example.yaml) for a full example.  
A minimal example:

```yaml
server:
  port: 8080
  host: 0.0.0.0
  workers: 4

  headers:
    - key: x-forwarded-for
      value: $ip

  upstreams:
    - id: server1
      host: 127.0.0.1
      port: 8081

    - id: server2
      host: 127.0.0.1
      port: 8082

  paths:
    - path: /api
      upstreams:
        - server1

    - path: /apiV2
      upstreams:
        - server2
        - server1
```

## Requirements

- **Python 3.8+**
- **Linux Kernel 4.5+** (for `EPOLLEXCLUSIVE` support)
- [Poetry](https://python-poetry.org/) for dependency management

---

## Getting Started

1. **Clone the repository:**

   ```sh
   git clone <your-repo-url>
   cd pyflexiproxy
   ```

2. **Install dependencies:**

   ```sh
   poetry install
   ```

3. **Configure your proxy:**

   - Edit `src/config.yaml` or copy and modify `src/config.example.yaml`.

4. **Run the proxy:**
   ```sh
   poetry run python src/main.py
   ```

---

## Running the Proxy

To start PyFlexiProxy, use the following command:

```sh
python3 src/main.py <config_file_path>
```

Replace `<config_file_path>` with the path to your YAML configuration file (e.g., `src/config.yaml`).

To display usage instructions or help, run:

```sh
python3 src/main.py -h
```

or

```sh
python3 src/main.py --help
```

This will print usage information and exit.

---

## Architecture Overview

- **Master Process:**  
  Loads configuration, sets up the listening socket, and spawns worker processes.

- **Worker Processes:**  
  Each worker uses Linux `epoll` (with `EPOLLEXCLUSIVE`) to efficiently handle multiple concurrent client connections.

- **Configurable Routing:**  
  Requests are routed to upstream servers based on path rules defined in the YAML config.

---

## License

MIT License

---

## Contributing

Contributions are welcome! Please open issues or submit pull requests for new features, bug fixes, or improvements.

---

## Acknowledgements

Inspired by NGINX and other high-performance proxies, but built from scratch in Python for flexibility and learning.
