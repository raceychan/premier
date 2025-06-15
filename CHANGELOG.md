# CHANGELOG

## version 0.4.9 (2025-06-14)

### Bug Fixes & Features

- **Dashboard Stats Tracking** - Fixed dashboard statistics tracking issues and improved real-time data accuracy
- **Dashboard Styling & Theme** - Enhanced dashboard visual appearance with improved styling and theme consistency
- ️**Configurable Server List** – Users can now define and manage servers directly from a configuration file

- **Load Balancing (Round Robin)** – Implemented round robin load balancer for distributing traffic evenly across servers

- ️**Circuit Breaker Support** – Added circuit breaker mechanism to improve fault tolerance and system resilience

### Refactoring

- **🔧 ASGI Architecture Refactor** - Major restructuring of ASGI components for better maintainability:
  - Separated forward service logic into dedicated module (`premier/asgi/forward.py`)
  - Created dedicated dashboard service (`premier/dashboard/service.py`) 
  - Implemented load balancer component (`premier/asgi/loadbalancer.py`)
  - Simplified main gateway module by extracting specialized services
  - Improved code organization and separation of concerns

### Chores

- **📄 License** - Added LICENSE file to the project
- **📖 Documentation** - Updated README.md with latest information
- **📋 Changelog** - Updated changelog documentation
- **📸 Dashboard Screenshots** - Added new dashboard screenshots showing configuration and statistics views

### Technical Improvements

- Enhanced dashboard service architecture with better separation of concerns
- Improved ASGI gateway performance through modular design
- Better error handling and logging in dashboard components
- Streamlined configuration management in dashboard

## version 0.4.8 (2025-06-14)

### Major Features

- **🎛️ Web Dashboard** - Built-in web GUI for real-time monitoring and configuration management
  - Live request/response metrics and performance analytics
  - Interactive configuration editor with YAML validation
  - Cache management and rate limiting dashboard
  - Health monitoring and system statistics
  - Available at `/premier/dashboard`

- **🚀 Complete Example Application** - Production-ready example with FastAPI backend
  - Comprehensive API endpoints demonstrating all Premier features
  - YAML configuration with path-specific policies
  - Documentation and testing guides
  - Dashboard integration showcase

- **📚 Enhanced Documentation** - Comprehensive documentation overhaul
  - Separate guides for web dashboard and examples
  - Updated README with better organization
  - Clear quick-start instructions
  - Production deployment guidance

### New Files & Components

- `premier/dashboard/` - Complete web dashboard implementation
- `example/` - Full-featured example application
- `docs/web-gui.md` - Web dashboard documentation
- `docs/examples.md` - Examples and tutorials guide
- Enhanced ASGI gateway with dashboard integration

### Improvements

- **ASGI Gateway Enhancement** - Better integration and dashboard support
- **Configuration Management** - Hot-reload configuration from web interface
- **Monitoring** - Real-time performance metrics and request analytics
- **User Experience** - Simplified setup with comprehensive examples

## v0.4.0 (2024-06-05)

### Chore

* chore: fix test ([`17ce3e4`](https://github.com/raceychan/pythrottler/commit/17ce3e49e7efbe6f9b2e3faf864692b791cfe0df))

* chore: dev ([`22be11c`](https://github.com/raceychan/pythrottler/commit/22be11c00787ef1f7333202cc9bd2475c1a9bed6))

* chore: readme ([`7d5a5bc`](https://github.com/raceychan/pythrottler/commit/7d5a5bccde4c0b37e9a94693ca5885af3aa0246f))

* chore: readme ([`f376b5b`](https://github.com/raceychan/pythrottler/commit/f376b5bf9ca29ff81b3934662fe92d89560b4094))

* chore: readme ([`bdcb13f`](https://github.com/raceychan/pythrottler/commit/bdcb13fb5cce7b72660a0a6e89eabea684b54fc1))

* chore: readme ([`9d14e9e`](https://github.com/raceychan/pythrottler/commit/9d14e9e32b38f41722d7fa4b07fe89358d977b64))

### Feature

* feat: better error message ([`b1c2523`](https://github.com/raceychan/pythrottler/commit/b1c25239c837aa4a08915011ee89add4f64bb8e2))

* feat: async queue ([`d621219`](https://github.com/raceychan/pythrottler/commit/d6212191abedd331d255aea80592af644bde1fe8))

* feat: aio ([`67d85c2`](https://github.com/raceychan/pythrottler/commit/67d85c2b10858dc700c6f5f42d0fc3dd34518ba9))

* feat: aio ([`710e934`](https://github.com/raceychan/pythrottler/commit/710e934057361ec95e513a5ef8d2d96e590b491a))

### Fix

* fix: make TaskQueue.put atomic using redis lua script ([`69a49aa`](https://github.com/raceychan/pythrottler/commit/69a49aa502a4946f60179c1036717365bfc7e402))

* fix: fixed asyncio throttler using asyncio.Lock ([`4811312`](https://github.com/raceychan/pythrottler/commit/481131212897f998b09173cd6b4f63f6f02c5ce8))

* fix: fix typing ([`29f4a76`](https://github.com/raceychan/pythrottler/commit/29f4a76c07c10a0ede157f5566f15f2a0f64c643))

### Refactor

* refactor: rewrite leaky bucket ([`5e38981`](https://github.com/raceychan/pythrottler/commit/5e389812832af6ef054858bd8c1a449f8b821092))

### Unknown

* chores: fix conflicts ([`07198a8`](https://github.com/raceychan/pythrottler/commit/07198a8739845c081f5bd84fc9e002310ae89ea3))

* Merge branch &#39;dev&#39;
adding async throttler for async function, also fixes a few bug in
threading case ([`630c8ed`](https://github.com/raceychan/pythrottler/commit/630c8ed6282a310c50fc26f57b42db2ff126bfb8))

* chores: last commit before merge ([`17110a9`](https://github.com/raceychan/pythrottler/commit/17110a92f57388369c3a2a6344051bde6aa99896))

* chores: fix type errors ([`0a69501`](https://github.com/raceychan/pythrottler/commit/0a6950191b67da0fa1a9c36a34e610cb2d0b4335))

* chores: refactor put script ([`fbca52e`](https://github.com/raceychan/pythrottler/commit/fbca52e190d02f369d74a64b8c6a6dc5132cb4e3))

* chores: fix typing ([`fccb598`](https://github.com/raceychan/pythrottler/commit/fccb598fb416d86119eed63d6508f8e971a6e161))

* wip: working on asyncio throttler ([`f933f10`](https://github.com/raceychan/pythrottler/commit/f933f10eb620a79b9801bd7cc7fb44657d759001))

* chores: remove setup.py ([`82b9ad6`](https://github.com/raceychan/pythrottler/commit/82b9ad612062a0d9755d61ddca4b34fbe23a8358))

* chores: test ([`6ff20d2`](https://github.com/raceychan/pythrottler/commit/6ff20d243a2f605fc250cf6926d90dd4d819393f))


## v0.3.0 (2024-04-08)

### Chore

* chore: readme ([`2429f50`](https://github.com/raceychan/pythrottler/commit/2429f5038b7bf241212821d1c9e7b9922b62b62a))

### Feature

* feat: refactor ([`e9f0c4d`](https://github.com/raceychan/pythrottler/commit/e9f0c4d45e9ff939e7c2942e03e50757f94e8333))

### Fix

* fix: minor errors ([`b8a630b`](https://github.com/raceychan/pythrottler/commit/b8a630bf59547bb76718dc378f0cdedecc507bc7))

### Unknown

* Merge pull request #1 from raceychan/dev

merge latest dev branch ([`8523182`](https://github.com/raceychan/pythrottler/commit/852318253642684714edf7bd447316b4b0453ff4))


## v0.2.0 (2024-04-03)

### Feature

* feat: leakybucket ([`b0dde75`](https://github.com/raceychan/pythrottler/commit/b0dde755497574e729e8eceee582063290c2663c))

* feat: readme ([`4105d39`](https://github.com/raceychan/pythrottler/commit/4105d397ca789ce21f969c0504ed4e3a897e966a))


## v0.1.0 (2024-04-02)

### Feature

* feat: rename ([`8565565`](https://github.com/raceychan/pythrottler/commit/856556584df7c773d19bd74562621ec3f74579a9))

* feat: readme ([`1b9932a`](https://github.com/raceychan/pythrottler/commit/1b9932a6fe4a7b8249051fef7eff0678358774e3))

* feat: readme ([`bb93c35`](https://github.com/raceychan/pythrottler/commit/bb93c3576fc721b56041e1adad730698e822126d))

* feat: readme ([`d1e2b16`](https://github.com/raceychan/pythrottler/commit/d1e2b16d36180508c846ff5e81d9e1204af4f3b1))

* feat: readme ([`3f406db`](https://github.com/raceychan/pythrottler/commit/3f406db6fb0b2820c2c1d4b60b2843417e4164a1))

* feat: readme ([`a397853`](https://github.com/raceychan/pythrottler/commit/a397853e8a5354ffbe1e0a921d77be3b9aedefa2))

* feat: readme ([`8584238`](https://github.com/raceychan/pythrottler/commit/858423825bc49e1c54fde543d1a7c6c419307cf6))

* feat: first commit ([`ba6abfc`](https://github.com/raceychan/pythrottler/commit/ba6abfc3dfc474c4cf5eb1e8951563fce51f1a7a))

* feat: first commit ([`4a83c49`](https://github.com/raceychan/pythrottler/commit/4a83c499ea5ee0631e3667e10e2526407890f5c6))

* feat: first commit ([`7be616c`](https://github.com/raceychan/pythrottler/commit/7be616ca6200e8452d9eabebc93b0bbec01c1291))


## version 0.4.3

Feature

- [x] `cache` 


refactor:

No longer support sync version of decorator, which means all decorated function would be async.


## version 0.4.6

- ✅ Implemented facade pattern with Premier class
- ✅ Added comprehensive logging support with ILogger interface
- ✅ Enhanced retry logic with detailed logging
- ✅ Improved timeout handling with logging
- ✅ Updated documentation and examples
- ✅ Removed legacy task queue implementation
- ✅ Made private functions properly private with underscore prefix

## version 0.4.7


Web GUI for config and monitor