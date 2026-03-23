# DIY Time Capsule: Ubuntu + Samba on ZFS

This guide helps you build a basic Time Machine server on Ubuntu using the ZFS layout from [Prepare a ZFS Backup Disk for Time Machine and rsync](disk-formatting-for-time-machine.md).

It covers the Apple-native backup path only: Samba, Bonjour advertisement, and the first Time Machine backup.

If you also want the parallel rsync + ZFS snapshot path, continue later with [Add the rsync Backup Path on Ubuntu](configure-rsync-backup-on-ubuntu.md).

## Before you begin

This guide assumes:

- the backup pool and base datasets already exist from [Prepare a ZFS Backup Disk for Time Machine and rsync](disk-formatting-for-time-machine.md)
- `backupz/timemachine` is mounted at `/backupz/timemachine`
- `backupz/rsync` is mounted at `/backupz/rsync`

## 1. Install base packages

```bash
sudo apt update
sudo apt install -y samba avahi-daemon acl
```

## 2. Choose the Samba account and create the group

You have two reasonable choices for the Samba login:

- use a dedicated backup-only account such as `timemachine`
- use your normal Unix username such as `chris`

The dedicated-account option is cleaner and is the example used below, but both approaches work.

Create the shared group and, if you want, the dedicated account:

```bash
sudo groupadd --force tmbackup
sudo useradd -M -s /usr/sbin/nologin -g tmbackup timemachine 2>/dev/null || true
sudo smbpasswd -a timemachine
```

If you prefer to use your normal username instead, add that user to `tmbackup` and create a Samba password for that account:

```bash
sudo groupadd --force tmbackup
sudo usermod -aG tmbackup chris
sudo smbpasswd -a chris
```

## 3. Prepare the Time Machine dataset path

```bash
sudo mkdir -p /backupz/timemachine
sudo chown root:tmbackup /backupz/timemachine
sudo chmod 2770 /backupz/timemachine
```

Using `2770` with group `tmbackup` means either a dedicated backup account or your normal username can write there as long as that user is in the `tmbackup` group.

If you want a monitoring user to have read access later, add an ACL instead of changing ownership:

```bash
sudo setfacl -m u:capsule-watch:rx /backupz/timemachine
```

## 4. Configure Samba for Time Machine

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

Add a Time Machine share:

```ini
[TimeCapsule]
path = /backupz/timemachine
browseable = yes
read only = no
guest ok = no
valid users = timemachine
create mask = 0660
directory mask = 2770
ea support = yes
fruit:time machine = yes
fruit:advertise_fullsync = true
# Optional cap inside Samba:
# fruit:time machine max size = 6000G
```

If you want to use your normal username instead of `timemachine`, change:

```ini
valid users = chris
```

If your config already defines `vfs objects` globally, merge `catia fruit streams_xattr` into the existing line instead of creating a duplicate key.

If you are repurposing an older Time Machine share, replace that old share block instead of keeping both. For example, if your current config still has a block such as `[backup-202603a]`, update that block to use the new `TimeCapsule` name, path, and `valid users` setting instead of leaving the stale share in place.

Validate before restart:

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

## 6. Quick check from a Mac

Before you start the first backup, do a quick sanity check from macOS.

### 6.1 Check direct SMB access

1. In Finder, choose `Go > Connect to Server`.
2. Connect to `smb://<ubuntu-server-ip>/TimeCapsule`.
3. Authenticate with the Samba account you chose, such as `timemachine` or `chris`.

If Finder opens the share successfully, Samba is working.

### 6.2 Check Time Machine discovery

1. On the Mac, open `System Settings > General > Time Machine`.
2. Click `Add Backup Disk`.
3. Look for `TimeCapsule` in the list.

If it appears there, Bonjour/mDNS discovery is also working.

If direct SMB access works but the share does not appear automatically in Time Machine, Samba is working and the problem is limited to discovery.

## 7. Select the backup disk in Time Machine and start the first backup

1. On the Mac, open `System Settings > General > Time Machine`.
2. Click `Add Backup Disk`.
3. Select `TimeCapsule` on `CHRIS-VOSTRO.local` or the equivalent hostname for your server.
4. Click `Set Up Disk`.
5. Authenticate with the Samba account you chose, such as `timemachine` or `chris`.
6. Start the initial backup if macOS does not begin automatically.

Optional CLI confirmation from the Mac after setup:

```bash
tmutil destinationinfo
tmutil status
```

If the share does not appear automatically in Time Machine settings, go back to the quick-check step and try connecting directly over SMB from Finder.

Server-side checks:

```bash
find /backupz/timemachine -maxdepth 1 -type d -name '*.sparsebundle'
find /backupz/timemachine -maxdepth 3 -type f -path '*/bands/*' -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | tail -n 20
```

If you only want a basic Time Machine server, you can stop here.

For deeper validation and restore testing, continue with [Verify and Restore Time Machine Backups](verify-and-restore-time-machine-backups.md).

## 8. What to do next

- For restore validation, use [Verify and Restore Time Machine Backups](verify-and-restore-time-machine-backups.md).
- To add the parallel rsync path on the server, use [Add the rsync Backup Path on Ubuntu](configure-rsync-backup-on-ubuntu.md).
- For Mac-side rsync configuration and automation, use [Set Up rsync Backups from macOS](rsync-backups-from-macos.md) after the Ubuntu-side rsync guide.
- For replica disks and `zfs send` / `zfs receive`, use [ZFS Replication and Backup Rotation](zfs-replication-and-rotation.md).

## What `avahi-daemon` does

`avahi-daemon` provides Bonjour/mDNS advertisement so Macs can discover the Samba Time Machine target on the local network.
