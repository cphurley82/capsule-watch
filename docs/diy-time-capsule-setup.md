# DIY Time Capsule: Ubuntu + Samba Setup

This guide helps you create a working Time Machine destination on Ubuntu before installing Capsule Watch.

For disk preparation and mounting details, see [Disk Formatting for Time Machine](disk-formatting-for-time-machine.md).

## 1. Install base packages

```bash
sudo apt update
sudo apt install -y samba avahi-daemon openssh-server
```

## 2. Create a backup user and group

Use a dedicated account for SMB authentication:

```bash
sudo groupadd --force tmbackup
sudo useradd -M -s /usr/sbin/nologin -g tmbackup timemachine
sudo smbpasswd -a timemachine
```

Use a different username if you prefer, but keep it dedicated to backup access.

## 3. Prepare the backup path

Assume your mounted backup root is `/srv/timecapsule` (or your chosen mount point from the disk-formatting guide):

```bash
sudo mkdir -p /srv/timecapsule
sudo chown root:tmbackup /srv/timecapsule
sudo chmod 2770 /srv/timecapsule
```

`2770` keeps the directory private and sets the setgid bit so files inherit the `tmbackup` group.

## 4. Configure Samba share

Edit `/etc/samba/smb.conf`:

```bash
sudoedit /etc/samba/smb.conf
```

Add or verify the following in `[global]`:

```ini
[global]
server min protocol = SMB2
vfs objects = catia fruit streams_xattr
fruit:aapl = yes
fruit:metadata = stream
fruit:encoding = native
fruit:model = TimeCapsule6,106
fruit:posix_rename = yes
fruit:veto_appledouble = no
fruit:nfs_aces = no
fruit:wipe_intentionally_left_blank_rfork = yes
fruit:delete_empty_adfiles = yes
```

Add a share block (or update your existing Time Machine share):

```ini
[TimeCapsule]
path = /srv/timecapsule
browseable = yes
read only = no
guest ok = no
valid users = timemachine
create mask = 0660
directory mask = 2770
ea support = yes
fruit:time machine = yes
fruit:advertise_fullsync = true
# Optional cap:
# fruit:time machine max size = 7000G
```

If you already have `vfs objects` set globally for other shares, merge `catia fruit streams_xattr` into that existing line rather than creating duplicate `vfs objects` entries.

Validate config before restart:

```bash
sudo testparm -s
```

## 5. Enable and restart services

```bash
sudo systemctl enable --now smbd avahi-daemon
sudo systemctl restart smbd avahi-daemon
```

Check status:

```bash
systemctl status smbd --no-pager --lines=0
systemctl status avahi-daemon --no-pager --lines=0
```

## 6. Connect from macOS and run first backup

1. On the Mac, open Finder and connect to `smb://<ubuntu-server-ip>/TimeCapsule`.
2. Authenticate with the Samba credentials (`timemachine` in this guide).
3. In Time Machine settings, select this share as a destination.
4. Start an initial backup.

Optional CLI confirmation from the Mac:

```bash
tmutil destinationinfo
tmutil status
```

## 7. Verify backup artifacts on Ubuntu

```bash
find /srv/timecapsule -maxdepth 1 -type d -name '*.sparsebundle'
```

You should see one sparsebundle directory per Mac that has backed up.

Check that band files are changing during/after a backup:

```bash
find /srv/timecapsule -maxdepth 3 -type f -path '*/bands/*' -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | tail -n 20
```

`*.sparsebundle` appearing as a directory is expected. Time Machine sparsebundles are package directories.

## 8. Next step

Once backups are working:

1. Continue with [Install Capsule Watch](install-capsule-watch.md).
2. Add ongoing validation and recovery checks from [Verify and restore Time Machine backups (CLI)](verify-and-restore-time-machine-backups.md).

## What `avahi-daemon` does

`avahi-daemon` provides Bonjour/mDNS advertisement so Macs can discover the Samba Time Machine target on the local network without manually entering the address each time.
