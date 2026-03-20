# Disk Formatting for Time Machine on Ubuntu

This guide prepares a backup volume for Samba Time Machine use.

## 1. Identify the target disk

```bash
lsblk -f
```

Choose the correct device (example: `/dev/sda`) and double-check before formatting.

## 2. Partition and format

Create a partition (example: `/dev/sda1`) using your preferred tool:

```bash
sudo fdisk /dev/sda
```

Format it as ext4:

```bash
sudo mkfs.ext4 -L TimeCapsule /dev/sda1
```

## 3. Create a mount point and configure `fstab`

```bash
sudo mkdir -p /srv/timecapsule
sudo blkid /dev/sda1
```

Add an `fstab` entry using the filesystem UUID:

```fstab
UUID=<disk-uuid> /srv/timecapsule ext4 defaults,noatime 0 2
```

Mount and verify:

```bash
sudo mount -a
df -hT /srv/timecapsule
```

## 4. Apply secure permissions for Samba access

Use a dedicated group (for example `tmbackup`) that your Samba backup user belongs to:

```bash
sudo groupadd --force tmbackup
sudo chown root:tmbackup /srv/timecapsule
sudo chmod 2770 /srv/timecapsule
```

Avoid `chmod 777` for backup storage directories.

## 5. Optional: enable ACL support

If you need to grant read access to monitoring users (for example `capsule-watch`) without changing primary ownership:

```bash
sudo apt install -y acl
sudo setfacl -m u:capsule-watch:rx /srv/timecapsule
```

## 6. Verify readiness for Time Machine

```bash
sudo touch /srv/timecapsule/.write-test && sudo rm /srv/timecapsule/.write-test
```

Then continue with [DIY Time Capsule setup](diy-time-capsule-setup.md) to configure Samba and verify macOS backups.

## 7. Best practices

- Use a dedicated disk when possible.
- Keep `noatime` for reduced write amplification.
- Run SMART checks regularly (`smartctl`).
- Keep at least 15-20% free space to avoid backup churn and fragmentation.
