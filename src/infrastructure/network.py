"""
Network service implementation
"""

import subprocess
import time
import json
from typing import List, Optional
from ..interfaces import INetworkService, NetworkInfo, ConnectionInfo, ConnectionStatus, ILogger
from ..domain.configuration import NetworkConfig
from ..domain.errors import NetworkError, ErrorCode, ErrorSeverity


class NetworkService(INetworkService):
    """Concrete implementation of network service"""
    
    def __init__(self, config: NetworkConfig, logger: Optional[ILogger] = None):
        self.config = config
        self.logger = logger
        self.current_connection: Optional[ConnectionInfo] = None
    
    def scan_networks(self) -> List[NetworkInfo]:
        """Scan for available WiFi networks"""
        networks = []
        
        try:
            if self.logger:
                self.logger.info("Starting WiFi network scan")
            
            # Use nmcli to scan for networks
            result = subprocess.run([
                'nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'
            ], capture_output=True, text=True, timeout=self.config.wifi_scan_timeout)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split(':')
                        if len(parts) >= 3:
                            ssid = parts[0]
                            try:
                                signal = int(parts[1]) if parts[1] else 0
                            except ValueError:
                                signal = 0
                            security = parts[2] if len(parts) > 2 else 'Open'
                            
                            if ssid:  # Skip empty SSIDs
                                networks.append(NetworkInfo(
                                    ssid=ssid,
                                    signal_strength=signal,
                                    security_type=security
                                ))
            
            if self.logger:
                self.logger.info(f"Found {len(networks)} WiFi networks")
            
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.error("WiFi scan timeout")
            raise NetworkError(
                ErrorCode.NETWORK_SCAN_FAILED,
                "WiFi scan timed out",
                ErrorSeverity.MEDIUM
            )
        except Exception as e:
            if self.logger:
                self.logger.error(f"WiFi scan failed: {e}")
            raise NetworkError(
                ErrorCode.NETWORK_SCAN_FAILED,
                f"Failed to scan networks: {str(e)}",
                ErrorSeverity.MEDIUM
            )
        
        return networks
    
    def connect_to_network(self, ssid: str, password: str) -> bool:
        """Connect to a WiFi network"""
        try:
            if self.logger:
                self.logger.info(f"Connecting to WiFi network: {ssid}")
            
            # First, create a connection profile
            result = subprocess.run([
                'nmcli', 'device', 'wifi', 'connect', ssid, 'password', password
            ], capture_output=True, text=True, timeout=self.config.connection_timeout)
            
            if result.returncode == 0:
                # Verify connection
                time.sleep(2)  # Give it a moment to establish
                if self.is_connected():
                    self.current_connection = ConnectionInfo(
                        status=ConnectionStatus.CONNECTED,
                        ssid=ssid
                    )
                    if self.logger:
                        self.logger.info(f"Successfully connected to {ssid}")
                    return True
            
            if self.logger:
                self.logger.error(f"Failed to connect to {ssid}: {result.stderr}")
            return False
            
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.error(f"Connection to {ssid} timed out")
            raise NetworkError(
                ErrorCode.NETWORK_TIMEOUT,
                f"Connection to {ssid} timed out",
                ErrorSeverity.MEDIUM
            )
        except Exception as e:
            if self.logger:
                self.logger.error(f"Connection failed: {e}")
            raise NetworkError(
                ErrorCode.NETWORK_CONNECTION_FAILED,
                f"Failed to connect to {ssid}: {str(e)}",
                ErrorSeverity.HIGH
            )
    
    def disconnect(self) -> bool:
        """Disconnect from current network"""
        try:
            result = subprocess.run([
                'nmcli', 'device', 'disconnect', self.config.interface_name
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                self.current_connection = None
                if self.logger:
                    self.logger.info("Disconnected from WiFi")
                return True
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Disconnect failed: {e}")
            return False
    
    def get_connection_info(self) -> ConnectionInfo:
        """Get current connection information"""
        if not self.is_connected():
            return ConnectionInfo(status=ConnectionStatus.DISCONNECTED)
        
        try:
            # Get detailed connection info
            result = subprocess.run([
                'nmcli', '-t', '-f', 'GENERAL.CONNECTION,IP4.ADDRESS', 'device', 'show', self.config.interface_name
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                ssid = None
                ip_address = None
                
                for line in lines:
                    if line.startswith('GENERAL.CONNECTION:'):
                        ssid = line.split(':', 1)[1]
                    elif line.startswith('IP4.ADDRESS[1]:'):
                        ip_part = line.split(':', 1)[1]
                        ip_address = ip_part.split('/')[0] if '/' in ip_part else ip_part
                
                return ConnectionInfo(
                    status=ConnectionStatus.CONNECTED,
                    ssid=ssid,
                    ip_address=ip_address
                )
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get connection info: {e}")
        
        return ConnectionInfo(status=ConnectionStatus.CONNECTED)
    
    def is_connected(self) -> bool:
        """Check if currently connected to WiFi"""
        try:
            result = subprocess.run([
                'nmcli', '-t', '-f', 'DEVICE,STATE', 'device', 'status'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.startswith(f'{self.config.interface_name}:'):
                        state = line.split(':')[1]
                        return state == 'connected'
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Connection check failed: {e}")
            return False
