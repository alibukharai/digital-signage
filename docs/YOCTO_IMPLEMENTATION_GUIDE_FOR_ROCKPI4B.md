# Yocto Linux Implementation Guide for ROCK Pi 4B+ Digital Signage

## Executive Summary

This guide provides comprehensive instructions for implementing a Yocto Linux-based system for the ROCK Pi 4B+ Digital Signage Provisioning System. This approach is recommended only if you need minimal footprint, fast boot times, or plan to develop custom hardware variants.

**⚠️ Warning: This approach requires 4-6 months of development time and embedded Linux expertise.**

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Development Environment Setup](#development-environment-setup)
3. [BSP Development for ROCK Pi 4B+](#bsp-development-for-rock-pi-4b)
4. [Custom Layer Creation](#custom-layer-creation)
5. [Application Integration](#application-integration)
6. [Boot Optimization](#boot-optimization)
7. [Security Hardening](#security-hardening)
8. [Build Automation](#build-automation)
9. [Custom Board Development](#custom-board-development)
10. [Production Deployment](#production-deployment)

## 🎯 Project Overview

### Target Specifications
- **Hardware**: ROCK Pi 4B+ (OP1 processor)
- **Boot Time**: < 15 seconds to application start
- **Storage**: < 500MB total footprint
- **Memory**: < 200MB runtime usage
- **Features**: Python 3.10+, Bluetooth 5.0, WiFi, HDMI 4K

### Yocto Project Structure
```
rockpi4bplus-yocto/
├── poky/                          # Yocto core
├── meta-openembedded/             # Additional layers
├── meta-rockpi4bplus/             # Custom BSP layer
├── meta-digital-signage/          # Application layer
├── build-rockpi4bplus/            # Build directory
└── scripts/                       # Automation scripts
```

## 🚀 Development Environment Setup

### Host System Requirements

**Recommended Host:**
- Ubuntu 22.04 LTS (x86_64)
- 16GB+ RAM
- 500GB+ SSD storage
- High-speed internet connection

### Initial Setup Script

```bash
#!/bin/bash
# setup-yocto-environment.sh

set -euo pipefail

YOCTO_VERSION="kirkstone"  # LTS version - stable until April 2026
WORKSPACE_DIR="$HOME/rockpi4bplus-yocto"
POKY_URL="git://git.yoctoproject.org/poky"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Install host dependencies
install_host_deps() {
    log "Installing host dependencies..."

    sudo apt update
    sudo apt install -y \
        gawk wget git diffstat unzip texinfo gcc build-essential \
        chrpath socat cpio python3 python3-pip python3-pexpect \
        xz-utils debianutils iputils-ping python3-git python3-jinja2 \
        libegl1-mesa libsdl1.2-dev pylint3 xterm python3-subunit \
        mesa-common-dev zstd liblz4-tool file locales

    # Configure locale
    sudo locale-gen en_US.UTF-8

    log "Host dependencies installed"
}

# Clone Yocto and layers
setup_yocto() {
    log "Setting up Yocto environment..."

    mkdir -p "$WORKSPACE_DIR"
    cd "$WORKSPACE_DIR"

    # Clone Poky (Yocto core)
    if [[ ! -d "poky" ]]; then
        git clone "$POKY_URL" -b "$YOCTO_VERSION"
    fi

    # Clone meta-openembedded
    if [[ ! -d "meta-openembedded" ]]; then
        git clone git://git.openembedded.org/meta-openembedded -b "$YOCTO_VERSION"
    fi

    # Clone meta-arm (for OP1 support)
    if [[ ! -d "meta-arm" ]]; then
        git clone https://git.yoctoproject.org/git/meta-arm -b "$YOCTO_VERSION"
    fi

    # Clone meta-rockchip (base for ROCK Pi support)
    if [[ ! -d "meta-rockchip" ]]; then
        git clone https://github.com/JeffyCN/meta-rockchip.git -b "$YOCTO_VERSION"
    fi

    log "Yocto environment setup complete"
}

# Initialize build environment
init_build() {
    log "Initializing build environment..."

    cd "$WORKSPACE_DIR/poky"
    source oe-init-build-env ../build-rockpi4bplus

    log "Build environment initialized at: $WORKSPACE_DIR/build-rockpi4bplus"
}

main() {
    log "Setting up Yocto development environment for ROCK Pi 4B+"

    install_host_deps
    setup_yocto
    init_build

    log "Setup complete! Next: Create custom BSP layer"
    log "cd $WORKSPACE_DIR/build-rockpi4bplus"
    log "source ../poky/oe-init-build-env"
}

main "$@"
```

## 🔧 BSP Development for ROCK Pi 4B+

### Custom BSP Layer Creation

```bash
#!/bin/bash
# create-rockpi4bplus-bsp.sh

cd $WORKSPACE_DIR
source poky/oe-init-build-env build-rockpi4bplus

# Create custom BSP layer
bitbake-layers create-layer ../meta-rockpi4bplus
cd ../meta-rockpi4bplus

# Layer structure
mkdir -p {conf/machine,recipes-kernel/linux,recipes-bsp/u-boot,recipes-graphics}
```

### Machine Configuration

**File: `meta-rockpi4bplus/conf/machine/rockpi4bplus.conf`**
```python
#@TYPE: Machine
#@NAME: ROCK Pi 4B Plus
#@DESCRIPTION: ROCK Pi 4B Plus with OP1 processor

MACHINEOVERRIDES =. "rockpi4:"

require conf/machine/include/rk3399.inc

# OP1 specific optimizations
DEFAULTTUNE = "cortexa72-cortexa53"

# Kernel selection
PREFERRED_PROVIDER_virtual/kernel = "linux-rockpi4bplus"
PREFERRED_VERSION_linux-rockpi4bplus = "5.15%"

# Bootloader
PREFERRED_PROVIDER_virtual/bootloader = "u-boot-rockpi4bplus"
PREFERRED_PROVIDER_u-boot = "u-boot-rockpi4bplus"

# GPU support
PREFERRED_PROVIDER_virtual/libgles2 = "rockchip-mali-midgard"
PREFERRED_PROVIDER_virtual/egl = "rockchip-mali-midgard"

# Storage
IMAGE_FSTYPES += "ext4 wic.bz2"
WIC_CREATE_EXTRA_ARGS = "--no-fstab-update"

# Boot configuration
UBOOT_MACHINE = "rock-pi-4-rk3399_defconfig"
UBOOT_ENTRYPOINT = "0x02080000"
UBOOT_LOADADDRESS = "0x02080000"

# Device tree
KERNEL_DEVICETREE = "rockchip/rk3399-rock-pi-4b-plus.dts"

# Serial console
SERIAL_CONSOLES = "1500000;ttyS2"

# Hardware features
MACHINE_FEATURES = "wifi bluetooth usbhost ext2 ext3 ext4 screen"
MACHINE_EXTRA_RRECOMMENDS = "kernel-modules"

# Graphics
DISTRO_FEATURES_append = " opengl"
```

### Custom Kernel Recipe

**File: `meta-rockpi4bplus/recipes-kernel/linux/linux-rockpi4bplus_5.15.bb`**
```python
SUMMARY = "Linux kernel for ROCK Pi 4B Plus"
DESCRIPTION = "Optimized Linux kernel for ROCK Pi 4B Plus with OP1 processor"

inherit kernel

LINUX_VERSION ?= "5.15.120"
LINUX_VERSION_EXTENSION = "-rockpi4bplus"

SRCREV = "v${LINUX_VERSION}"
SRC_URI = "git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git;branch=linux-5.15.y;protocol=https"

# Device tree and patches
SRC_URI += " \
    file://rockpi4bplus.dts \
    file://rockpi4bplus-bluetooth.patch \
    file://rockpi4bplus-wifi.patch \
    file://rockpi4bplus-gpio.patch \
    file://rockpi4bplus-performance.patch \
    file://defconfig \
"

S = "${WORKDIR}/git"

COMPATIBLE_MACHINE = "rockpi4bplus"

# Kernel configuration optimizations
do_configure_prepend() {
    # Copy optimized defconfig
    cp ${WORKDIR}/defconfig ${S}/arch/arm64/configs/rockpi4bplus_defconfig

    # Apply OP1 specific optimizations
    echo "CONFIG_CPUFREQ_DT=y" >> ${S}/arch/arm64/configs/rockpi4bplus_defconfig
    echo "CONFIG_ARM_RK3399_DMC_DEVFREQ=y" >> ${S}/arch/arm64/configs/rockpi4bplus_defconfig
    echo "CONFIG_DEVFREQ_GOV_PERFORMANCE=y" >> ${S}/arch/arm64/configs/rockpi4bplus_defconfig

    # Bluetooth 5.0 optimizations
    echo "CONFIG_BT_HCIUART_BCM=y" >> ${S}/arch/arm64/configs/rockpi4bplus_defconfig
    echo "CONFIG_BT_HCIUART_3WIRE=y" >> ${S}/arch/arm64/configs/rockpi4bplus_defconfig

    # Remove unnecessary drivers to reduce boot time
    echo "# CONFIG_SOUND_SOC_ROCKCHIP is not set" >> ${S}/arch/arm64/configs/rockpi4bplus_defconfig
    echo "# CONFIG_DRM_ROCKCHIP is not set" >> ${S}/arch/arm64/configs/rockpi4bplus_defconfig
}

KCONFIG_MODE = "--alldefconfig"
KBUILD_DEFCONFIG = "rockpi4bplus_defconfig"
```

### Device Tree for ROCK Pi 4B+

**File: `meta-rockpi4bplus/recipes-kernel/linux/files/rockpi4bplus.dts`**
```dts
// SPDX-License-Identifier: (GPL-2.0+ OR MIT)
/*
 * Copyright (c) 2025 ROCK Pi 4B Plus Digital Signage
 * Optimized device tree for digital signage application
 */

/dts-v1/;
#include "rk3399.dtsi"
#include "rk3399-opp.dtsi"

/ {
    model = "ROCK Pi 4B Plus Digital Signage";
    compatible = "radxa,rockpi4b-plus", "rockchip,rk3399";

    chosen {
        bootargs = "earlycon=uart8250,mmio32,0xff1a0000 console=ttyS2,1500000n8";
        stdout-path = "serial2:1500000n8";
    };

    // Memory configuration for OP1
    memory@0 {
        device_type = "memory";
        reg = <0x0 0x0 0x0 0x80000000>; // 2GB base, expandable to 4GB
    };

    // GPIO LEDs for status indication
    gpio_leds {
        compatible = "gpio-leds";
        pinctrl-names = "default";
        pinctrl-0 = <&status_led_pins>;

        status_red {
            label = "status:red";
            gpios = <&gpio0 RK_PB5 GPIO_ACTIVE_HIGH>;
            default-state = "off";
        };

        status_green {
            label = "status:green";
            gpios = <&gpio0 RK_PB6 GPIO_ACTIVE_HIGH>;
            default-state = "off";
        };

        status_blue {
            label = "status:blue";
            gpios = <&gpio0 RK_PB7 GPIO_ACTIVE_HIGH>;
            default-state = "off";
        };
    };

    // GPIO buttons
    gpio_keys {
        compatible = "gpio-keys";
        pinctrl-names = "default";
        pinctrl-0 = <&button_pins>;

        reset_button {
            label = "Reset Button";
            gpios = <&gpio1 RK_PA0 GPIO_ACTIVE_LOW>;
            linux,code = <KEY_RESTART>;
            debounce-interval = <100>;
        };

        config_button {
            label = "Config Button";
            gpios = <&gpio1 RK_PA1 GPIO_ACTIVE_LOW>;
            linux,code = <KEY_CONFIG>;
            debounce-interval = <100>;
        };
    };

    // Power management for OP1
    cpu_opp_table: cpu-opp-table {
        compatible = "operating-points-v2";
        opp-shared;

        // Optimized frequencies for digital signage workload
        opp-408000000 {
            opp-hz = /bits/ 64 <408000000>;
            opp-microvolt = <800000>;
            clock-latency-ns = <40000>;
        };
        opp-600000000 {
            opp-hz = /bits/ 64 <600000000>;
            opp-microvolt = <825000>;
        };
        opp-816000000 {
            opp-hz = /bits/ 64 <816000000>;
            opp-microvolt = <850000>;
        };
        opp-1008000000 {
            opp-hz = /bits/ 64 <1008000000>;
            opp-microvolt = <925000>;
        };
        opp-1200000000 {
            opp-hz = /bits/ 64 <1200000000>;
            opp-microvolt = <1000000>;
        };
        opp-1416000000 {
            opp-hz = /bits/ 64 <1416000000>;
            opp-microvolt = <1100000>;
        };
        opp-1608000000 {
            opp-hz = /bits/ 64 <1608000000>;
            opp-microvolt = <1175000>;
        };
        opp-1800000000 {
            opp-hz = /bits/ 64 <1800000000>;
            opp-microvolt = <1275000>;
        };
        opp-2000000000 {
            opp-hz = /bits/ 64 <2000000000>;
            opp-microvolt = <1350000>;
        };
    };
};

// WiFi/Bluetooth module configuration
&uart0 {
    status = "okay";
    pinctrl-names = "default";
    pinctrl-0 = <&uart0_xfer &uart0_cts>;

    bluetooth {
        compatible = "brcm,bcm43438-bt";
        clocks = <&rk808 1>;
        clock-names = "ext_clock";
        device-wakeup-gpios = <&gpio2 RK_PD3 GPIO_ACTIVE_HIGH>;
        host-wakeup-gpios = <&gpio0 RK_PA4 GPIO_ACTIVE_HIGH>;
        shutdown-gpios = <&gpio0 RK_PB1 GPIO_ACTIVE_HIGH>;
        pinctrl-names = "default";
        pinctrl-0 = <&bt_host_wake_l &bt_wake_l &bt_reg_on_h>;
    };
};

// HDMI configuration for 4K support
&hdmi {
    status = "okay";
    pinctrl-names = "default";
    pinctrl-0 = <&hdmi_cec>;
};

&hdmi_in {
    hdmi_in_vopb: endpoint@0 {
        reg = <0>;
        remote-endpoint = <&vopb_out_hdmi>;
    };
    hdmi_in_vopl: endpoint@1 {
        reg = <1>;
        remote-endpoint = <&vopl_out_hdmi>;
    };
};

// GPU configuration for Mali-T860MP4
&gpu {
    status = "okay";
    mali-supply = <&vdd_gpu>;
};

// Pinctrl definitions
&pinctrl {
    status_led_pins: status-led-pins {
        rockchip,pins =
            <0 RK_PB5 RK_FUNC_GPIO &pcfg_pull_none>,
            <0 RK_PB6 RK_FUNC_GPIO &pcfg_pull_none>,
            <0 RK_PB7 RK_FUNC_GPIO &pcfg_pull_none>;
    };

    button_pins: button-pins {
        rockchip,pins =
            <1 RK_PA0 RK_FUNC_GPIO &pcfg_pull_up>,
            <1 RK_PA1 RK_FUNC_GPIO &pcfg_pull_up>;
    };
};
```

## 📦 Custom Layer Creation

### Application Layer Structure

```bash
# Create application layer
cd $WORKSPACE_DIR
bitbake-layers create-layer meta-digital-signage

# Layer structure
meta-digital-signage/
├── conf/layer.conf
├── recipes-apps/
│   └── digital-signage/
│       ├── digital-signage_1.0.bb
│       └── files/
├── recipes-core/
│   └── images/
│       └── digital-signage-image.bb
├── recipes-python/
│   └── python3-signage-deps/
└── recipes-support/
    └── signage-configs/
```

### Layer Configuration

**File: `meta-digital-signage/conf/layer.conf`**
```python
# Layer configuration for digital signage application
BBPATH .= ":${LAYERDIR}"

BBFILES += "${LAYERDIR}/recipes-*/*/*.bb \
            ${LAYERDIR}/recipes-*/*/*.bbappend"

BBFILE_COLLECTIONS += "digital-signage"
BBFILE_PATTERN_digital-signage = "^${LAYERDIR}/"
BBFILE_PRIORITY_digital-signage = "10"

LAYERVERSION_digital-signage = "1"
LAYERSERIES_COMPAT_digital-signage = "kirkstone"

# Dependencies
LAYERDEPENDS_digital-signage = "core openembedded-layer meta-python"
```

### Python Dependencies Recipe

**File: `meta-digital-signage/recipes-python/python3-signage-deps/python3-signage-deps_1.0.bb`**
```python
SUMMARY = "Python dependencies for digital signage application"
DESCRIPTION = "All Python packages required for the ROCK Pi 4B+ digital signage system"

LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

# Python dependencies
RDEPENDS_${PN} = " \
    python3-asyncio \
    python3-bluetooth \
    python3-cryptography \
    python3-json \
    python3-logging \
    python3-threading \
    python3-datetime \
    python3-subprocess \
    python3-signal \
    python3-pathlib \
    python3-dataclasses \
    python3-typing-extensions \
"

# Custom Python packages
RDEPENDS_${PN} += " \
    python3-bleak \
    python3-qrcode \
    python3-pillow \
    python3-opencv \
    python3-psutil \
    python3-pydantic \
"

# System packages
RDEPENDS_${PN} += " \
    bluez5 \
    wireless-tools \
    wpa-supplicant \
    openssh \
    systemd \
"

# Install empty package (dependencies only)
do_install() {
    # Create empty package - dependencies are the important part
    :
}

ALLOW_EMPTY_${PN} = "1"
```

### Main Application Recipe

**File: `meta-digital-signage/recipes-apps/digital-signage/digital-signage_1.0.bb`**
```python
SUMMARY = "ROCK Pi 4B+ Digital Signage Provisioning Application"
DESCRIPTION = "Complete provisioning system for digital signage deployment"

LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=..." # Add actual MD5 of your license

SRC_URI = " \
    git://github.com/your-org/rockpi-provisioning.git;protocol=https;branch=yocto-integration \
    file://digital-signage.service \
    file://digital-signage.conf \
"

SRCREV = "${AUTOREV}"

S = "${WORKDIR}/git"

inherit setuptools3 systemd

SYSTEMD_SERVICE_${PN} = "digital-signage.service"
SYSTEMD_AUTO_ENABLE = "enable"

# Runtime dependencies
RDEPENDS_${PN} = " \
    python3-signage-deps \
    systemd \
    dbus \
"

do_install_append() {
    # Install systemd service
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/digital-signage.service ${D}${systemd_system_unitdir}

    # Install configuration
    install -d ${D}${sysconfdir}/digital-signage
    install -m 0644 ${WORKDIR}/digital-signage.conf ${D}${sysconfdir}/digital-signage/

    # Create runtime directories
    install -d ${D}${localstatedir}/lib/digital-signage
    install -d ${D}${localstatedir}/log/digital-signage

    # Install application
    install -d ${D}${bindir}
    install -d ${D}${libdir}/python3.10/site-packages/digital_signage

    # Copy source code
    cp -r ${S}/src/* ${D}${libdir}/python3.10/site-packages/digital_signage/

    # Create startup script
    cat > ${D}${bindir}/digital-signage << 'EOF'
#!/bin/sh
cd /usr/lib/python3.10/site-packages
exec python3 -m digital_signage "$@"
EOF
    chmod +x ${D}${bindir}/digital-signage
}

FILES_${PN} += " \
    ${systemd_system_unitdir}/digital-signage.service \
    ${sysconfdir}/digital-signage/ \
    ${localstatedir}/lib/digital-signage/ \
    ${localstatedir}/log/digital-signage/ \
"
```

### Custom Image Recipe

**File: `meta-digital-signage/recipes-core/images/digital-signage-image.bb`**
```python
SUMMARY = "Minimal digital signage image for ROCK Pi 4B+"
DESCRIPTION = "Optimized Linux image for digital signage with fast boot"

inherit core-image

# Base image features
IMAGE_FEATURES += "read-only-rootfs"

# Package groups
IMAGE_INSTALL = " \
    packagegroup-core-boot \
    packagegroup-core-ssh-openssh \
    ${CORE_IMAGE_EXTRA_INSTALL} \
"

# Core system packages
IMAGE_INSTALL += " \
    systemd \
    systemd-serialgetty \
    dbus \
    util-linux \
    e2fsprogs-resize2fs \
"

# Hardware support
IMAGE_INSTALL += " \
    kernel-modules \
    linux-firmware \
    rockchip-mali-midgard \
    bluetooth-firmware \
    wireless-firmware \
"

# Application packages
IMAGE_INSTALL += " \
    digital-signage \
    python3-signage-deps \
"

# Boot optimization
IMAGE_INSTALL += " \
    systemd-boot-optimization \
    kernel-module-autoload \
"

# Debugging tools (remove for production)
IMAGE_INSTALL += " \
    htop \
    strace \
    tcpdump \
"

# Image optimization
IMAGE_OVERHEAD_FACTOR = "1.1"
IMAGE_ROOTFS_EXTRA_SPACE = "0"

# Read-only rootfs with overlays
IMAGE_FEATURES += "read-only-rootfs"

# Remove package manager from final image
IMAGE_FEATURES_remove = "package-management"

# Size optimization
PACKAGE_EXCLUDE = " \
    perl \
    python3-pip \
    gcc \
    make \
    autoconf \
    automake \
"

export IMAGE_BASENAME = "digital-signage-image"
```

## ⚡ Boot Optimization

### Fast Boot Configuration

**File: `meta-digital-signage/recipes-core/systemd/systemd_%.bbappend`**
```python
# Systemd boot optimizations

FILESEXTRAPATHS_prepend := "${THISDIR}/files:"

SRC_URI += " \
    file://fast-boot.conf \
    file://disable-unused-services.conf \
"

do_install_append() {
    # Install boot optimization configs
    install -d ${D}${sysconfdir}/systemd/system.conf.d
    install -m 0644 ${WORKDIR}/fast-boot.conf ${D}${sysconfdir}/systemd/system.conf.d/

    # Disable unused services
    install -d ${D}${sysconfdir}/systemd/system
    install -m 0644 ${WORKDIR}/disable-unused-services.conf ${D}${sysconfdir}/systemd/system/
}
```

**File: `meta-digital-signage/recipes-core/systemd/files/fast-boot.conf`**
```ini
[Manager]
# Boot speed optimizations
DefaultTimeoutStartSec=10s
DefaultTimeoutStopSec=5s
DefaultRestartSec=1s

# Reduce log verbosity
LogLevel=warning
LogTarget=console

# Memory optimizations
RuntimeWatchdogSec=30s
RebootWatchdogSec=2min

# Faster service startup
DefaultLimitNOFILE=1024
DefaultTasksMax=1024
```

### Kernel Boot Optimization

**File: `meta-rockpi4bplus/recipes-kernel/linux/files/fast-boot.patch`**
```diff
--- a/arch/arm64/configs/rockpi4bplus_defconfig
+++ b/arch/arm64/configs/rockpi4bplus_defconfig
@@ -1,5 +1,15 @@
 # ROCK Pi 4B Plus optimized configuration

+# Boot speed optimizations
+CONFIG_CC_OPTIMIZE_FOR_SIZE=y
+CONFIG_EMBEDDED=y
+CONFIG_EXPERT=y
+CONFIG_KALLSYMS=n
+CONFIG_BUG=n
+CONFIG_ELF_CORE=n
+CONFIG_BASE_FULL=n
+CONFIG_FUTEX=y
+CONFIG_EPOLL=y
+
 # CPU Configuration for OP1
 CONFIG_ARM64=y
 CONFIG_ARCH_ROCKCHIP=y
```

## 🔒 Security Hardening

### Security Configuration Layer

**File: `meta-digital-signage/recipes-security/security-config/security-config_1.0.bb`**
```python
SUMMARY = "Security hardening configuration"
DESCRIPTION = "Security policies and configurations for digital signage"

LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

SRC_URI = " \
    file://security-policies.conf \
    file://firewall-rules.sh \
    file://audit-rules.conf \
"

inherit systemd

do_install() {
    # Security policies
    install -d ${D}${sysconfdir}/security
    install -m 0644 ${WORKDIR}/security-policies.conf ${D}${sysconfdir}/security/

    # Firewall setup
    install -d ${D}${sysconfdir}/init.d
    install -m 0755 ${WORKDIR}/firewall-rules.sh ${D}${sysconfdir}/init.d/

    # Audit configuration
    install -d ${D}${sysconfdir}/audit
    install -m 0644 ${WORKDIR}/audit-rules.conf ${D}${sysconfdir}/audit/
}

RDEPENDS_${PN} = "iptables auditd"
```

### Read-Only Root Filesystem

**File: `meta-digital-signage/recipes-core/images/digital-signage-image.bbappend`**
```python
# Read-only root filesystem with overlay

EXTRA_IMAGE_FEATURES += "read-only-rootfs"

# Overlay filesystem for writable areas
IMAGE_INSTALL_append = " \
    overlayfs-tools \
    initramfs-overlay \
"

# Writable mount points
VOLATILE_LOG_DIR = "yes"
VOLATILE_TMP_DIR = "yes"

# Custom fstab for overlays
do_image_prepend() {
    cat >> ${IMAGE_ROOTFS}/etc/fstab << 'EOF'
# Overlay filesystems for writable areas
tmpfs /tmp tmpfs defaults,nodev,nosuid,size=10M 0 0
tmpfs /var/log tmpfs defaults,nodev,nosuid,size=50M 0 0
tmpfs /var/lib/digital-signage tmpfs defaults,nodev,nosuid,size=20M 0 0
EOF
}
```

## 🏗️ Build Automation

### Automated Build Script

**File: `scripts/build-production.sh`**
```bash
#!/bin/bash
# Automated production build for ROCK Pi 4B+

set -euo pipefail

WORKSPACE_DIR="$HOME/rockpi4bplus-yocto"
BUILD_DIR="$WORKSPACE_DIR/build-rockpi4bplus"
DEPLOY_DIR="$BUILD_DIR/tmp/deploy/images/rockpi4bplus"
OUTPUT_DIR="$HOME/rockpi-releases"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Build configuration
setup_build_config() {
    log "Configuring build environment..."

    cd "$BUILD_DIR"
    source ../poky/oe-init-build-env .

    # Configure local.conf
    cat >> conf/local.conf << 'EOF'
# Production build configuration
MACHINE = "rockpi4bplus"
DISTRO = "poky"

# Build optimizations
BB_NUMBER_THREADS = "8"
PARALLEL_MAKE = "-j 8"

# Package management
PACKAGE_CLASSES = "package_rpm"
EXTRA_IMAGE_FEATURES ?= "debug-tweaks"

# Security features
DISTRO_FEATURES_append = " systemd security"
VIRTUAL-RUNTIME_init_manager = "systemd"

# Storage optimization
INHERIT += "rm_work"
RM_WORK_EXCLUDE += "digital-signage-image"

# Version tracking
BUILDHISTORY_COMMIT = "1"
EOF

    # Configure layers
    bitbake-layers add-layer ../meta-openembedded/meta-oe
    bitbake-layers add-layer ../meta-openembedded/meta-python
    bitbake-layers add-layer ../meta-openembedded/meta-networking
    bitbake-layers add-layer ../meta-arm/meta-arm
    bitbake-layers add-layer ../meta-arm/meta-arm-toolchain
    bitbake-layers add-layer ../meta-rockchip
    bitbake-layers add-layer ../meta-rockpi4bplus
    bitbake-layers add-layer ../meta-digital-signage

    log "Build configuration complete"
}

# Clean build
clean_build() {
    log "Cleaning previous build artifacts..."

    cd "$BUILD_DIR"
    bitbake -c cleanall digital-signage-image
    rm -rf tmp/work/*rockpi4bplus*

    log "Clean complete"
}

# Build image
build_image() {
    log "Starting production build..."

    cd "$BUILD_DIR"

    # Build with timing
    time bitbake digital-signage-image

    if [[ $? -eq 0 ]]; then
        log "Build completed successfully"
    else
        log "Build failed!"
        exit 1
    fi
}

# Package release
package_release() {
    log "Packaging release artifacts..."

    mkdir -p "$OUTPUT_DIR"
    cd "$DEPLOY_DIR"

    # Version info
    local version="$(date +%Y%m%d-%H%M%S)"
    local release_dir="$OUTPUT_DIR/rockpi4bplus-digital-signage-$version"
    mkdir -p "$release_dir"

    # Copy artifacts
    cp digital-signage-image-rockpi4bplus.ext4 "$release_dir/"
    cp digital-signage-image-rockpi4bplus.wic.bz2 "$release_dir/"
    cp u-boot-rockpi4bplus.img "$release_dir/"
    cp Image "$release_dir/"
    cp rk3399-rock-pi-4b-plus.dtb "$release_dir/"

    # Create deployment script
    cat > "$release_dir/flash-image.sh" << 'EOF'
#!/bin/bash
# Flash ROCK Pi 4B+ digital signage image

DEVICE=${1:-/dev/sdX}

if [[ "$DEVICE" == "/dev/sdX" ]]; then
    echo "Usage: $0 /dev/sdX"
    echo "Replace sdX with your actual device (e.g., /dev/sdb)"
    exit 1
fi

echo "Flashing to $DEVICE..."
bunzip2 -c digital-signage-image-rockpi4bplus.wic.bz2 | sudo dd of="$DEVICE" bs=4M status=progress conv=fsync

echo "Flash complete! Insert SD card into ROCK Pi 4B+ and boot."
EOF
    chmod +x "$release_dir/flash-image.sh"

    # Create checksum
    cd "$release_dir"
    sha256sum * > SHA256SUMS

    log "Release packaged: $release_dir"
}

# Generate build report
generate_report() {
    log "Generating build report..."

    cd "$BUILD_DIR"

    cat > "$OUTPUT_DIR/build-report-$(date +%Y%m%d).txt" << EOF
ROCK Pi 4B+ Digital Signage Build Report
========================================

Build Date: $(date)
Build Host: $(hostname)
Build User: $(whoami)

Image Details:
$(ls -lh $DEPLOY_DIR/digital-signage-image-*.ext4)

Package List:
$(bitbake -g digital-signage-image && cat pn-buildlist | wc -l) packages

Build Time:
$(cat build-time.log 2>/dev/null || echo "N/A")

Storage Usage:
Root FS: $(du -sh $DEPLOY_DIR/digital-signage-image-*.ext4)
Total: $(du -sh $DEPLOY_DIR/)
EOF

    log "Build report generated"
}

# Main build process
main() {
    log "=== ROCK Pi 4B+ Production Build ==="

    setup_build_config
    clean_build
    build_image
    package_release
    generate_report

    log "=== Build Complete ==="
    log "Release available at: $OUTPUT_DIR"
}

main "$@"
```

## 📱 Custom Board Development

### Creating a Custom Machine Configuration

If you're developing custom hardware based on ROCK Pi 4B+:

**File: `meta-custom-board/conf/machine/custom-signage-board.conf`**
```python
#@TYPE: Machine
#@NAME: Custom Digital Signage Board
#@DESCRIPTION: Custom board based on ROCK Pi 4B+ with additional features

# Inherit from ROCK Pi 4B+
require conf/machine/rockpi4bplus.conf

MACHINEOVERRIDES =. "custom-signage:"

# Custom hardware features
MACHINE_FEATURES_append = " custom-leds custom-sensors custom-io"

# Custom device tree
KERNEL_DEVICETREE = "rockchip/custom-signage-board.dts"

# Additional drivers
MACHINE_EXTRA_RRECOMMENDS_append = " \
    custom-led-driver \
    custom-sensor-driver \
    custom-io-driver \
"

# Custom bootloader configuration
UBOOT_MACHINE = "custom-signage-board_defconfig"

# Custom power management
PREFERRED_PROVIDER_virtual/power-management = "custom-power-manager"

# Additional GPIOs
MACHINE_GPIO_PINS = "40 custom-expansion-header"

# Custom storage layout
EXTRA_IMAGEDEPENDS += "custom-partition-layout"
```

### Custom Hardware Integration

**File: `meta-custom-board/recipes-kernel/linux/files/custom-signage-board.dts`**
```dts
// Custom board device tree
/dts-v1/;
#include "rockpi4bplus.dts"

/ {
    model = "Custom Digital Signage Board v1.0";
    compatible = "company,custom-signage-v1", "radxa,rockpi4b-plus", "rockchip,rk3399";

    // Custom GPIO expander
    gpio_expander: gpio-expander@20 {
        compatible = "nxp,pca9555";
        reg = <0x20>;
        gpio-controller;
        #gpio-cells = <2>;
        interrupt-parent = <&gpio1>;
        interrupts = <RK_PA7 IRQ_TYPE_LEVEL_LOW>;
    };

    // Custom LED matrix
    led_matrix {
        compatible = "custom,led-matrix-controller";
        gpios = <&gpio_expander 0 GPIO_ACTIVE_HIGH>,
                <&gpio_expander 1 GPIO_ACTIVE_HIGH>,
                <&gpio_expander 2 GPIO_ACTIVE_HIGH>;
        matrix-size = <8 8>;
    };

    // Custom sensor array
    sensor_array {
        compatible = "custom,environmental-sensors";
        temperature-sensor = <&i2c_temp_sensor>;
        humidity-sensor = <&i2c_humidity_sensor>;
        light-sensor = <&i2c_light_sensor>;
        motion-sensor = <&gpio_motion_sensor>;
    };

    // Custom power management
    power_controller {
        compatible = "custom,power-controller";
        enable-gpios = <&gpio0 RK_PC1 GPIO_ACTIVE_HIGH>;
        power-good-gpios = <&gpio0 RK_PC2 GPIO_ACTIVE_HIGH>;

        regulators {
            vdd_custom: regulator-custom {
                regulator-name = "vdd_custom";
                regulator-min-microvolt = <3300000>;
                regulator-max-microvolt = <3300000>;
                regulator-always-on;
                regulator-boot-on;
            };
        };
    };
};

// I2C sensors
&i2c1 {
    status = "okay";

    temp_sensor: temperature@48 {
        compatible = "ti,tmp102";
        reg = <0x48>;
        interrupt-parent = <&gpio1>;
        interrupts = <RK_PB0 IRQ_TYPE_LEVEL_LOW>;
    };

    humidity_sensor: humidity@40 {
        compatible = "sensirion,sht3x";
        reg = <0x40>;
    };

    light_sensor: light@23 {
        compatible = "rohm,bh1750";
        reg = <0x23>;
    };
};

// Custom SPI devices
&spi1 {
    status = "okay";

    custom_display: display@0 {
        compatible = "custom,lcd-controller";
        reg = <0>;
        spi-max-frequency = <10000000>;
        reset-gpios = <&gpio2 RK_PB1 GPIO_ACTIVE_LOW>;
        dc-gpios = <&gpio2 RK_PB2 GPIO_ACTIVE_HIGH>;
    };
};
```

## 🚀 Production Deployment

### Deployment Automation

**File: `scripts/deploy-production.sh`**
```bash
#!/bin/bash
# Production deployment script for custom boards

set -euo pipefail

RELEASE_DIR="${1:-}"
TARGET_DEVICE="${2:-}"
BOARD_TYPE="${3:-rockpi4bplus}"

if [[ -z "$RELEASE_DIR" || -z "$TARGET_DEVICE" ]]; then
    echo "Usage: $0 <release_directory> <target_device> [board_type]"
    echo "Example: $0 /path/to/release /dev/sdb rockpi4bplus"
    exit 1
fi

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Verify release
verify_release() {
    log "Verifying release integrity..."

    cd "$RELEASE_DIR"

    if [[ ! -f "SHA256SUMS" ]]; then
        echo "ERROR: SHA256SUMS not found"
        exit 1
    fi

    if ! sha256sum -c SHA256SUMS; then
        echo "ERROR: Checksum verification failed"
        exit 1
    fi

    log "Release verification passed"
}

# Flash image
flash_image() {
    log "Flashing image to $TARGET_DEVICE..."

    # Safety check
    if [[ ! -b "$TARGET_DEVICE" ]]; then
        echo "ERROR: $TARGET_DEVICE is not a block device"
        exit 1
    fi

    # Unmount device
    sudo umount ${TARGET_DEVICE}* 2>/dev/null || true

    # Flash
    local image_file="digital-signage-image-${BOARD_TYPE}.wic.bz2"
    if [[ -f "$image_file" ]]; then
        bunzip2 -c "$image_file" | sudo dd of="$TARGET_DEVICE" bs=4M status=progress conv=fsync
    else
        echo "ERROR: Image file not found: $image_file"
        exit 1
    fi

    sync
    log "Flash complete"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."

    # Mount and check filesystem
    mkdir -p /tmp/mount_check
    sudo mount ${TARGET_DEVICE}1 /tmp/mount_check

    if [[ -f "/tmp/mount_check/usr/bin/digital-signage" ]]; then
        log "Application found on target device"
    else
        echo "ERROR: Application not found on target device"
        sudo umount /tmp/mount_check
        exit 1
    fi

    sudo umount /tmp/mount_check
    rmdir /tmp/mount_check

    log "Deployment verification passed"
}

# Main deployment
main() {
    log "=== Production Deployment ==="
    log "Release: $RELEASE_DIR"
    log "Target: $TARGET_DEVICE"
    log "Board: $BOARD_TYPE"

    verify_release
    flash_image
    verify_deployment

    log "=== Deployment Complete ==="
    log "Insert device into target board and power on"
}

main "$@"
```

### Production Testing Script

**File: `scripts/production-test.sh`**
```bash
#!/bin/bash
# Production testing for deployed boards

set -euo pipefail

BOARD_IP="${1:-}"
TEST_TIMEOUT=300

if [[ -z "$BOARD_IP" ]]; then
    echo "Usage: $0 <board_ip_address>"
    exit 1
fi

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Test SSH connectivity
test_ssh() {
    log "Testing SSH connectivity..."

    if timeout 30 ssh -o ConnectTimeout=10 root@"$BOARD_IP" 'echo "SSH OK"'; then
        log "SSH connectivity: PASS"
        return 0
    else
        log "SSH connectivity: FAIL"
        return 1
    fi
}

# Test application
test_application() {
    log "Testing digital signage application..."

    local app_status=$(ssh root@"$BOARD_IP" 'systemctl is-active digital-signage')

    if [[ "$app_status" == "active" ]]; then
        log "Application status: PASS"
    else
        log "Application status: FAIL ($app_status)"
        return 1
    fi

    # Test application API
    if ssh root@"$BOARD_IP" 'curl -s http://localhost:8080/health | grep -q "healthy"'; then
        log "Application health: PASS"
    else
        log "Application health: FAIL"
        return 1
    fi
}

# Test hardware
test_hardware() {
    log "Testing hardware components..."

    # Test Bluetooth
    if ssh root@"$BOARD_IP" 'bluetoothctl show | grep -q "Powered: yes"'; then
        log "Bluetooth: PASS"
    else
        log "Bluetooth: FAIL"
        return 1
    fi

    # Test WiFi
    if ssh root@"$BOARD_IP" 'iwconfig 2>/dev/null | grep -q "IEEE 802.11"'; then
        log "WiFi: PASS"
    else
        log "WiFi: FAIL"
        return 1
    fi

    # Test display
    if ssh root@"$BOARD_IP" 'xrandr --query | grep -q "connected"'; then
        log "Display: PASS"
    else
        log "Display: FAIL"
        return 1
    fi
}

# Performance test
test_performance() {
    log "Testing performance..."

    # Boot time
    local boot_time=$(ssh root@"$BOARD_IP" 'systemd-analyze | grep "Startup finished" | grep -o "[0-9.]*s$"')
    log "Boot time: $boot_time"

    # Memory usage
    local memory_usage=$(ssh root@"$BOARD_IP" 'free -m | grep "Mem:" | awk "{print \$3/\$2*100}"')
    log "Memory usage: ${memory_usage}%"

    # CPU temperature
    local cpu_temp=$(ssh root@"$BOARD_IP" 'cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null' || echo "0")
    cpu_temp=$((cpu_temp / 1000))
    log "CPU temperature: ${cpu_temp}°C"
}

# Main test suite
main() {
    log "=== Production Test Suite ==="
    log "Target board: $BOARD_IP"

    local tests_passed=0
    local tests_total=4

    if test_ssh; then ((tests_passed++)); fi
    if test_application; then ((tests_passed++)); fi
    if test_hardware; then ((tests_passed++)); fi
    test_performance && ((tests_passed++))

    log "=== Test Results ==="
    log "Passed: $tests_passed/$tests_total"

    if [[ $tests_passed -eq $tests_total ]]; then
        log "ALL TESTS PASSED - Board ready for production"
        exit 0
    else
        log "SOME TESTS FAILED - Board requires attention"
        exit 1
    fi
}

main "$@"
```

## 📊 Performance Metrics

### Expected Yocto Performance vs Debian

| Metric | Yocto Linux | Radxa Debian 11 | Improvement |
|--------|-------------|-----------------|-------------|
| **Boot Time** | 8-15 seconds | 30-50 seconds | 2-3x faster |
| **Memory Usage** | 150-250 MB | 450-700 MB | 2-3x less |
| **Storage Size** | 200-500 MB | 2-3 GB | 4-6x smaller |
| **Application Start** | 2-5 seconds | 5-10 seconds | 2x faster |
| **Security Surface** | Minimal | Standard | Reduced |

## 🎯 Conclusion

### When to Choose Yocto:
- ✅ Boot time < 15 seconds is critical
- ✅ Storage space extremely limited (< 1GB)
- ✅ Building 1000+ units
- ✅ Have embedded Linux expertise
- ✅ 6+ months development time available

### Development Investment:
- **Time**: 4-6 months vs 1-2 months for Debian
- **Expertise**: Embedded Linux skills required
- **Maintenance**: Ongoing BSP maintenance needed
- **Cost**: $85,000+ vs $25,000 for Debian approach

**Recommendation**: For most digital signage deployments, **Radxa Debian 11** provides the optimal balance of development speed, cost-effectiveness, and functionality. Choose Yocto only if you have specific requirements that justify the additional complexity and development time.
