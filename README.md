# NZB Media Information Integration for Unfolded Circle Remote Two/3

[![GitHub Release](https://img.shields.io/github/release/mase1981/uc-intg-nzbinfo.svg)](https://github.com/mase1981/uc-intg-nzbinfo/releases)
[![GitHub License](https://img.shields.io/github/license/mase1981/uc-intg-nzbinfo.svg)](https://github.com/mase1981/uc-intg-nzbinfo/blob/main/LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg)](https://paypal.me/mmiyara)


**IMPORTANT DISCLAIMER**: This integration is designed solely for monitoring and displaying information from NZB media management applications. It provides READ-ONLY access to application status and statistics. The author explicitly disclaims any liability for the intended use of this software and does not support or endorse the downloading of protected or copyrighted content. This software is provided "as is" for informational purposes only.

Custom NZB media information integration for your Unfolded Circle Remote Two/3. Transform your remote into a comprehensive monitoring dashboard for SABnzbd, NZBGet, Radarr, Sonarr, Lidarr, Readarr, Overseerr, and Bazarr applications.

## 🎯 Purpose and Scope

**This integration is INFORMATION ONLY and provides:**
- Real-time status monitoring of NZB applications
- Download queue information and statistics
- System health and performance metrics
- Application availability status

**This integration does NOT and will NEVER:**
- Initiate downloads or add content
- Provide control functions for downloads
- Support or enable downloading of protected content
- Offer any functionality beyond read-only monitoring

## 🔍 Supported Applications

### Download Clients
- **SABnzbd**: Download queue, speed, remaining time, history statistics
- **NZBGet**: Active downloads, queue status, server connections, post-processing

### Media Management
- **Radarr**: Movie collection status, wanted/missing items, system health
- **Sonarr**: TV series monitoring, calendar events, disk space
- **Lidarr**: Music collection management, artist monitoring
- **Readarr**: Book collection tracking, author monitoring

### Request Management
- **Overseerr**: Pending requests, user statistics, service status

### Subtitles
- **Bazarr**: Subtitle download status, language statistics, health monitoring

## 📋 Prerequisites

### Hardware Requirements
- **Unfolded Circle Remote Two/3**
- **Network Access**: Remote must reach your media server applications
- **Running Applications**: At least one supported NZB application with API enabled

### Software Requirements

#### NZB Applications Setup
Each application must have its API enabled and accessible:

1. **SABnzbd**: API key from Config → General → API Key
2. **NZBGet**: Enable API in Settings → Security
3. **Radarr/Sonarr/Lidarr/Readarr**: API key from Settings → General → API Key
4. **Overseerr**: API key from Settings → General → API Key
5. **Bazarr**: API key from Settings → General → API Key

#### Network Requirements
- **HTTP/HTTPS Access**: Default ports (7878, 8989, 8080, etc.)
- **Same Network**: Recommended for optimal performance
- **Firewall**: Ensure application ports are accessible

## 🚀 Quick Start

### Step 1: Verify Application APIs

#### Check API Access
Test connectivity to your applications:

```bash
# SABnzbd
http://YOUR_SERVER_IP:8080/api?mode=queue&apikey=YOUR_API_KEY

# Radarr
http://YOUR_SERVER_IP:7878/api/v3/system/status?apikey=YOUR_API_KEY

# Sonarr
http://YOUR_SERVER_IP:8989/api/v3/system/status?apikey=YOUR_API_KEY
```

#### Gather Required Information
For each application you want to monitor:
- **IP Address** and **Port**
- **API Key**
- **Base URL** (if using reverse proxy)
- **SSL/TLS** configuration (if applicable)

### Step 2: Install Integration on Remote

#### Via Remote Two/3 Web Interface
1. **Access Web Configurator**
   ```
   http://YOUR_REMOTE_IP/configurator
   ```

2. **Install Integration**
   - Navigate to: **Integrations** → **Add New** / **Install Custom**
   - Upload: **uc-intg-nzbinfo-***
   - Click: **Upload**

3. **Configure Applications**
   - Select applications to monitor
   - Enter IP addresses and API keys
   - Test connections automatically
   - Complete setup

4. **Add Entities**
   - **NZB Media Monitor** (Media Player) - for application monitoring
   - Add to your desired activities

## 🎮 Using the Integration

### Media Information Display (Media Player Entity)

#### Source Selection
Use the **SELECT SOURCE** feature to switch between application views:

| Source | Information Displayed |
|--------|----------------------|
| **Overview** | All applications status summary |
| **SABnzbd** | Queue status, download speed, remaining time |
| **NZBGet** | Active downloads, post-processing status |
| **Radarr** | Movie collection stats, wanted items |
| **Sonarr** | TV series monitoring, upcoming episodes |
| **Lidarr** | Music collection status, artist monitoring |
| **Readarr** | Book collection tracking, author status |
| **Overseerr** | Pending requests, user activity |
| **Bazarr** | Subtitle status, language coverage |

#### Real-time Updates
- **Refresh Rate**: 30 seconds (configurable)
- **Connection Status**: Shows offline status if application unreachable
- **Data Persistence**: Maintains last known values during brief disconnections
- **Error Handling**: Graceful degradation when applications are unavailable

### Information Categories

#### Download Clients
**SABnzbd Display:**
- In queue with statistics
- Last file

**NZBGet Display:**
- In queue with statistics
- Last file

#### Media Management
**Radarr/Sonarr Display:**
- In queue with statistics
- Last file

**Lidarr/Readarr Display:**
- In queue with statistics
- Last file

#### Request Management
**Overseerr Display:**
- Recent request activity

## 🔧 Configuration

### Environment Variables (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `UC_INTEGRATION_HTTP_PORT` | Integration HTTP port | `9090` |
| `UC_INTEGRATION_INTERFACE` | Bind interface | `0.0.0.0` |
| `UC_CONFIG_HOME` | Configuration directory | `./` |

### Configuration File

Located at: `config.json` in integration directory

```json
{
  "applications": {
    "sabnzbd": {
      "enabled": true,
      "host": "192.168.1.100",
      "port": 8080,
      "api_key": "your_api_key_here",
      "ssl": false
    },
    "radarr": {
      "enabled": true,
      "host": "192.168.1.100",
      "port": 7878,
      "api_key": "your_api_key_here",
      "ssl": false
    }
  },
  "refresh_interval": 30,
  "timeout": 10
}
```

## 🛠️ Troubleshooting
### Debug Information

**Check integration status**:
```bash
# Via web configurator
http://YOUR_REMOTE_IP/configurator → Integrations → NZB Media → Status
```

**Test application APIs manually**:
```bash
# SABnzbd queue status
curl "http://SERVER_IP:8080/api?mode=queue&apikey=YOUR_KEY"

# Radarr system status
curl "http://SERVER_IP:7878/api/v3/system/status?apikey=YOUR_KEY"

# Sonarr calendar
curl "http://SERVER_IP:8989/api/v3/calendar?apikey=YOUR_KEY"
```


## 📄 Legal and Disclaimer

### Terms of Use

**READ CAREFULLY**: By using this software, you acknowledge and agree that:

1. **Information Only**: This software provides read-only monitoring capabilities
2. **No Download Control**: No functionality to initiate, control, or manage downloads
3. **User Responsibility**: You are solely responsible for your use of connected applications
4. **Legal Compliance**: You must ensure all activities comply with local laws
5. **No Warranty**: Software provided "as is" without any warranty or guarantee

### Limitation of Liability

The author and contributors of this software:
- **Disclaim all liability** for any use of this software
- **Do not endorse** downloading of copyrighted or protected content
- **Provide no support** for illegal activities
- **Accept no responsibility** for user actions or consequences

### Privacy and Data

This integration:
- **Does not collect** personal data or usage statistics
- **Does not transmit** data outside your local network
- **Stores only** configuration data locally on your Remote device
- **Accesses only** read-only API endpoints you explicitly configure

## 📄 License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Community Resources

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-nzbinfo/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)

### Support Limitations

**The author provides limited support and will NOT:**
- Assist with any and all downloading activities
- Help configure applications for copyrighted content
- Provide guidance on bypassing content protection
- Support any use that violates terms of service
- Review or accept any logs that will have any data related to download activities

---

**Made with ❤️ for the Unfolded Circle Community**

*Monitor your media applications responsibly and in compliance with all applicable laws.*

**Author**: Meir Miyara  