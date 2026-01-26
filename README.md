# NZB Info Manager Integration for Unfolded Circle Remote 2/3

Monitor and control newsgroup applications like SABnzbd, NZBget, Sonarr, Radarr, Lidarr, Readarr, Bazarr, and Overseerr directly from your Unfolded Circle Remote 2 or Remote 3.

![NZB Info Manager](https://img.shields.io/badge/NZB-Info%20Manager-blue)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-nzbinfo?style=flat-square)](https://github.com/mase1981/uc-intg-nzbinfo/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-nzbinfo?style=flat-square)](https://github.com/mase1981/uc-intg-nzbinfo/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://unfolded.community/)
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-nzbinfo/total?style=flat-square)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA&style=flat-square)](https://github.com/sponsors/mase1981)

---

## ⚠️ Important Disclaimer

This integration is designed solely for monitoring and displaying information from NZB media management applications. It provides **READ-ONLY** access to application status and statistics. The author explicitly disclaims any liability for the intended use of this software and does not support or endorse the downloading of protected or copyrighted content. This software is provided "as is" for informational purposes only.

---

## ❤️ Support Development ❤️

If you find this integration useful, consider supporting development:

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/mase1981)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/mmiyara)

Your support helps maintain this integration. Thank you! ❤️

---

## Features

This integration provides comprehensive monitoring of NZB media management applications through their native APIs, delivering seamless integration with your Unfolded Circle Remote.

### 📥 **Download Clients**

#### **SABnzbd**
- Download queue monitoring with real-time statistics
- Download speed and remaining time tracking
- History statistics and completion status

#### **NZBget**
- Active downloads and queue status
- Server connection monitoring
- Post-processing status tracking

### 🎬 **Media Management**

#### **Radarr** (Movies)
- Movie collection status and statistics
- Wanted/missing items tracking
- System health monitoring

#### **Sonarr** (TV Series)
- TV series monitoring and calendar events
- Disk space and system status
- Episode tracking

#### **Lidarr** (Music)
- Music collection management
- Artist monitoring
- Album tracking

#### **Readarr** (Books)
- Book collection tracking
- Author monitoring
- Reading list management

### 🎭 **Request & Subtitle Management**

#### **Overseerr**
- Pending requests monitoring
- User statistics tracking
- Service status

#### **Bazarr**
- Subtitle download status
- Language statistics
- Health monitoring

### 📊 **Real-time Monitoring**

- Application status (Online/Offline)
- Queue information and statistics
- Download progress tracking
- System health metrics
- Connection status indicators

### **Application Support**

- **SABnzbd** - Usenet download client
- **NZBget** - Efficient Usenet downloader
- **Radarr** - Movie collection manager
- **Sonarr** - TV series manager
- **Lidarr** - Music collection manager
- **Readarr** - Book collection manager
- **Overseerr** - Request management system
- **Bazarr** - Subtitle management

## Installation

### Option 1: Remote Web Interface (Recommended)

1. Navigate to the [**Releases**](https://github.com/mase1981/uc-intg-nzbinfo/releases) page
2. Download the latest `uc-intg-uc_intg_nzbinfo-<version>-aarch64.tar.gz` file
3. Open your remote's web interface (`http://your-remote-ip`)
4. Go to **Settings** → **Integrations** → **Add Integration**
5. Click **Upload** and select the downloaded `.tar.gz` file

### Option 2: Docker (Advanced Users)

The integration can be run as a standalone Docker container:

**Docker Compose:**
```yaml
services:
  uc-intg-nzbinfo:
    image: ghcr.io/mase1981/uc-intg-nzbinfo:latest
    container_name: uc-intg-nzbinfo
    network_mode: host
    volumes:
      - </local/path>:/data
    environment:
      - UC_CONFIG_HOME=/data
      - UC_INTEGRATION_HTTP_PORT=9091
      - UC_INTEGRATION_INTERFACE=0.0.0.0
      - PYTHONPATH=/app
    restart: unless-stopped
```

**Docker Run:**
```bash
docker run -d --name uc-nzbinfo --restart unless-stopped --network host -v nzbinfo-config:/app/config -e UC_CONFIG_HOME=/app/config -e UC_INTEGRATION_INTERFACE=0.0.0.0 -e UC_INTEGRATION_HTTP_PORT=9091 -e PYTHONPATH=/app ghcr.io/mase1981/uc-intg-nzbinfo:latest
```

## Configuration

### Step 1: Prepare Your Applications

**IMPORTANT**: Applications must have API access enabled and be accessible on your network.

#### Gather API Keys:
1. **SABnzbd**: Config → General → API Key
2. **NZBget**: Settings → Security → Enable API
3. **Radarr/Sonarr/Lidarr/Readarr**: Settings → General → API Key
4. **Overseerr**: Settings → General → API Key
5. **Bazarr**: Settings → General → API Key

#### Network Requirements:
- **HTTP/HTTPS Access**: Applications must be accessible (default ports: SABnzbd 8080, Radarr 7878, Sonarr 8989, etc.)
- **Same Network**: Recommended for optimal performance
- **Firewall**: Allow HTTP traffic to application ports

### Step 2: Setup Integration

1. After installation, go to **Settings** → **Integrations**
2. The NZB Info Manager integration should appear in **Available Integrations**
3. Click **"Configure"** to begin setup:

#### **Configuration:**
- **Enable Applications**: Select which applications to monitor (SABnzbd, NZBget, Radarr, Sonarr, Lidarr, Readarr, Bazarr, Overseerr)
- **Enter Host:Port**: For each enabled application (e.g., 192.168.1.100:8080)
- **Enter API Key**: Paste the API key from each application
- **Test Connection**: Integration verifies connectivity automatically
- Click **Complete Setup**

#### **Connection Test:**
- Integration verifies each application's connectivity
- API authentication confirmed
- Setup fails if applications are unreachable or authentication fails

4. Integration will create entities:
   - **Media Player**: `media_player.nzb_media_monitor` for application monitoring
   - Use SELECT SOURCE to switch between application views

## Using the Integration

### Media Player Entity

The media player entity provides comprehensive monitoring:

- **Source Selection**: Switch between application views (Overview, SABnzbd, NZBget, Radarr, Sonarr, Lidarr, Readarr, Overseerr, Bazarr)
- **Real-time Updates**: 30-second refresh interval (configurable)
- **Status Display**: Connection status, queue information, statistics
- **Multi-Application View**: Monitor all applications from a single entity

### Application Views

| Source | Information Displayed |
|--------|----------------------|
| Overview | All applications status summary |
| SABnzbd | Queue status, download speed, remaining time |
| NZBget | Active downloads, post-processing status |
| Radarr | Movie collection stats, wanted items |
| Sonarr | TV series monitoring, upcoming episodes |
| Lidarr | Music collection status, artist monitoring |
| Readarr | Book collection tracking, author status |
| Overseerr | Pending requests, user activity |
| Bazarr | Subtitle status, language coverage |

## Credits

- **Developer**: Meir Miyara
- **Applications**: SABnzbd, NZBget, Radarr, Sonarr, Lidarr, Readarr, Overseerr, Bazarr
- **Unfolded Circle**: Remote 2/3 integration framework (ucapi)
- **Community**: Testing and feedback from UC community

## License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) - see LICENSE file for details.

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-nzbinfo/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle Community**

**Thank You**: Meir Miyara

*Monitor your media applications responsibly and in compliance with all applicable laws.*
