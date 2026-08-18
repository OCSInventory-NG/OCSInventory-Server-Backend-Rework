from django.db import migrations


def create_linux_extended_debian_sections(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")

    template = Template.objects.get(name="Linux Extended (Debian based)", os="DEB")

    sections = [
        {
            "name": "BIOS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "dmidecode",
            "options": {"multiple": False, "separator": None},
            "template": template,
        },
        {
            "name": "CONTROLLERS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "lspci -nnvmm",
            "options": {"multiple": False, "separator": "Slot:"},
            "template": template,
        },
        {
            "name": "CPUS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "LANG=C lscpu && dmidecode -t processor",
            "options": {"multiple": False, "separator": None},
            "template": template,
        },
        {
            "name": "DRIVES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "df -TP | awk 'NR==1{next} {printf \"Filesystem: %s\\nType: %s\\n1K-blocks: %s\\nAvailable: %s\\nUse%%: %s\\nMounted: %s\\nSize_MB: %.2f\\nAvail_MB: %.2f\\n---\\n\", $1, $2, $3, $5, $6, $7, $3/1024, $5/1024}'",
            "options": {"multiple": False, "separator": "---"},
            "template": template,
        },
        {
            "name": "TEAM VIEWER",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "sudo teamviewer info | sed 's/\\x1b\\[[0-9;]*m//g' | grep -E \"TeamViewer ID|^\\s+TeamViewer\\s+[0-9]\"",
            "options": {"multiple": False, "separator": None},
            "template": template,
        },
        {
            "name": "INPUTS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'awk -v RS=\'\' \'{ if(match($0,/Bus=[0-9a-fA-F]+/)){ bus_val=substr($0,RSTART,RLENGTH); sub(/Bus=/,"",bus_val); }else{ bus_val=""; } if(match($0,/Vendor=[0-9a-fA-F]+/)){ vendor_val=substr($0,RSTART,RLENGTH); sub(/Vendor=/,"",vendor_val); }else{ vendor_val=""; } if(match($0,/Product=[0-9a-fA-F]+/)){ product_val=substr($0,RSTART,RLENGTH); sub(/Product=/,"",product_val); }else{ product_val=""; } if(match($0,/Name="[^"]+"/)){ name_val=substr($0,RSTART,RLENGTH); sub(/Name="/,"",name_val); sub(/"$/,"",name_val); }else{ name_val=""; } if(match($0,/Sysfs=[^ \\n]+/)){ sysfs_val=substr($0,RSTART,RLENGTH); sub(/Sysfs=/,"",sysfs_val); }else{ sysfs_val=""; } b_clean=toupper(bus_val); sub(/^0+/,"",b_clean); if(b_clean=="")b_clean="0"; bus_hex=(length(b_clean)==1?"0x0" b_clean:"0x" b_clean); bus=(bus_hex=="0x01")?"PCI":(bus_hex=="0x02")?"ISAPNP":(bus_hex=="0x03")?"USB":(bus_hex=="0x04")?"HIL":(bus_hex=="0x05")?"Bluetooth":(bus_hex=="0x06")?"Virtual":(bus_hex=="0x10")?"ISA":(bus_hex=="0x11")?"i8042":(bus_hex=="0x12")?"XT Keyboard":(bus_hex=="0x13")?"RS232":(bus_hex=="0x14")?"Gameport":(bus_hex=="0x15")?"Parallel Port":(bus_hex=="0x16")?"Amiga":(bus_hex=="0x17")?"ADB (Apple Desktop Bus)":(bus_hex=="0x18")?"I2C":(bus_hex=="0x19")?"Host":(bus_hex=="0x1A")?"GSC":(bus_hex=="0x1B")?"Atari":(bus_hex=="0x1C")?"SPI":(bus_hex=="0x1D")?"RMI":(bus_hex=="0x1E")?"CEC":(bus_hex=="0x1F")?"Intel ISHTP":(bus_hex=="0x20")?"AMD SFH":"Unknown (" bus_hex ")"; print "Type: " bus; print "Bus: " bus_val; vendor=tolower(vendor_val); print "Vendor: " vendor; product=tolower(product_val); print "Product: " product; if(vendor!=""){ cmd="cat /usr/share/hwdata/usb.ids /var/lib/usbutils/usb.ids /usr/share/misc/usb.ids 2>/dev/null | grep -i \\x27^" vendor " \\x27 | head -n1 | cut -c7-"; manufacturer=""; cmd | getline manufacturer; close(cmd); print "Manufacturer: " manufacturer; if(product!=""){ cmd2="cat /usr/share/hwdata/usb.ids /var/lib/usbutils/usb.ids /usr/share/misc/usb.ids 2>/dev/null | awk \\x27/^" vendor " /{flag=1; next} /^[^[:space:]]/{flag=0} flag && /^[[:space:]]+" product " /{print substr($0, index($0, \\x27" product "\\x27) + 5); exit}\\x27"; description=""; cmd2 | getline description; close(cmd2); print "Description: " description; } if(name_val!="")print "Caption: " name_val; if(sysfs_val!="")print "Interface: " sysfs_val; print "---"; } }\' /proc/bus/input/devices',
            "options": {"multiple": False, "separator": "---"},
            "template": template,
        },
        {
            "name": "LOCAL USERS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "cat /etc/passwd",
            "options": {"multiple": True, "separator": None},
            "template": template,
        },
        {
            "name": "MEMORIES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "dmidecode -t 17 -q",
            "options": {"multiple": False, "separator": "Memory Device"},
            "template": template,
        },
        {
            "name": "MONITORS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'for f in /sys/class/drm/*/edid; do [ "$(cat "${f%/*}/status" 2>/dev/null)" = "connected" ] || continue; echo -e "\\n$f\\n"; vc=$(di-edid-decode "$f" 2>/dev/null | awk \'/Manufacturer:/ {print $2}\'); [ -n "$vc" ] && echo "Vendor: $(grep -m 1 "^$vc" /usr/share/hwdata/pnp.ids 2>/dev/null | cut -f2- || echo "$vc")"; di-edid-decode "$f"; echo "\\n==="; done',
            "options": {"multiple": False, "separator": "==="},
            "template": template,
        },
        {
            "name": "NETWORKS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'for dev_path in /sys/class/net/*; do dev="${dev_path##*/}"; [[ -d "/sys/class/net/$dev/wireless" ]] && type="wifi" || { [[ "$dev" == lo ]] && type="loopback" || type="ethernet"; }; speed_raw=$(cat "/sys/class/net/$dev/speed" 2>/dev/null || echo 0); mtu=$(cat "/sys/class/net/$dev/mtu" 2>/dev/null); mac_addr=$(cat "/sys/class/net/$dev/address" 2>/dev/null); state=$(cat "/sys/class/net/$dev/operstate" 2>/dev/null); gw=$(ip route show default 2>/dev/null | grep "dev $dev" | awk \'{print $3}\'); gw6=$(ip -6 route show default 2>/dev/null | grep "dev $dev" | awk \'{print $3}\'); ip4_cidrs=$(ip -4 -o addr show dev "$dev" 2>/dev/null | awk \'{print $4}\'); [[ -z "$ip4_cidrs" ]] && ip4_cidrs=" "; for ip4_cidr in $ip4_cidrs; do echo "Description: $dev"; echo "Type: $type"; if [[ "$speed_raw" == "-1" ]]; then echo "Speed: -1"; elif [[ "$speed_raw" -ge 1000 ]]; then echo "Speed: $((speed_raw / 1000)) Gbps"; else echo "Speed: ${speed_raw} Mbps"; fi; echo "MTU: $mtu"; echo "MACAddress: $mac_addr"; echo "Status: $state"; ip="${ip4_cidr%%/*}"; prefix="${ip4_cidr#*/}"; [[ "$ip" == "$prefix" ]] && prefix=""; echo "IPAddress: $ip"; if [[ -n "$prefix" && "$prefix" =~ ^[0-9]+$ ]]; then mask=$(( 0xFFFFFFFF << (32 - prefix) & 0xFFFFFFFF )); netmask="$(( (mask >> 24) & 0xFF )).$(( (mask >> 16) & 0xFF )).$(( (mask >> 8) & 0xFF )).$(( mask & 0xFF ))"; echo "Netmask: $netmask"; fi; echo "Gateway: $gw"; if [[ -n "$ip" && -n "$prefix" && "$prefix" =~ ^[0-9]+$ ]]; then IFS=\'.\' read -r i1 i2 i3 i4 <<< "$ip"; ip_bin=$(( (i1 << 24) + (i2 << 16) + (i3 << 8) + i4 )); mask_bin=$(( 0xFFFFFFFF << (32 - prefix) & 0xFFFFFFFF )); net_bin=$(( ip_bin & mask_bin )); net_ip=$(printf "%d.%d.%d.%d" $(( (net_bin >> 24) & 0xFF )) $(( (net_bin >> 16) & 0xFF )) $(( (net_bin >> 8) & 0xFF )) $(( net_bin & 0xFF ))); echo "NetworkNumber: $net_ip"; else echo "NetworkNumber: "; fi; echo "---"; done; ip6_cidrs=$(ip -6 -o addr show dev "$dev" 2>/dev/null | awk \'{print $4}\'); if [[ -n "$ip6_cidrs" ]]; then for ip6_cidr in $ip6_cidrs; do ip6="${ip6_cidr%%/*}"; prefix6="${ip6_cidr#*/}"; if [[ "$prefix6" =~ ^[0-9]+$ ]]; then mask6=$(printf \'%s\\n\' $(for i in {0..7}; do bits=$(( (prefix6-16*i)>16 ? 16 : (prefix6-16*i>0 ? prefix6-16*i : 0) )); printf \'%04x:\' $(( ((1<<bits)-1) << (16-bits) )); done) | sed \'s/:$//\' | sed -E \':a;s/(^|:)0{1,4}(:0{1,4}){1,}/::/;ta\'); else mask6=""; fi; ip6_network=$(ip -6 route show dev "$dev" 2>/dev/null | head -n1 | awk \'{print $1}\'); echo "Description: $dev"; echo "Type: $type"; if [[ "$speed_raw" == "-1" ]]; then echo "Speed: -1"; elif [[ "$speed_raw" -ge 1000 ]]; then echo "Speed: $((speed_raw / 1000)) Gbps"; else echo "Speed: ${speed_raw} Mbps"; fi; echo "MTU: $mtu"; echo "MACAddress: $mac_addr"; echo "Status: $state"; echo "IPAddress: $ip6"; echo "Netmask: $mask6"; echo "Gateway: $gw6"; echo "NetworkNumber: $ip6_network"; echo "---"; done; fi; done',
            "options": {"multiple": False, "separator": "---"},
            "template": template,
        },
        {
            "name": "PORTS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "dmidecode -t connector",
            "options": {"multiple": False, "separator": "Handle"},
            "template": template,
        },
        {
            "name": "PRINTERS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'for name in $(lpstat -p 2>/dev/null | awk \'{print $2}\'); do description=$(lpstat -l -p "$name" | grep "Description" | cut -d: -f2- | sed \'s/^ *//\'); port=$(lpstat -v "$name" | awk -F\': \' \'{print $2}\'); driver=$(lpoptions -p "$name" | grep "printer-make-and-model" | cut -d"\'" -f2); echo "Name: $name"; echo "Description: $description"; echo "Port: $port"; echo "Driver: $driver"; echo "---"; done',
            "options": {"multiple": False, "separator": "---"},
            "template": template,
        },
        {
            "name": "SLOTS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "dmidecode -t slot",
            "options": {"multiple": False, "separator": "System Slot Information"},
            "template": template,
        },
        {
            "name": "SOUNDS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "lspci -nn | grep -i audio | cut -d ' ' -f1 | xargs -I{} lspci -vmm -s {}",
            "options": {"multiple": False, "separator": "Slot:"},
            "template": template,
        },
        {
            "name": "STORAGES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'for storage in $(lsblk -dno NAME,TYPE | awk \'$2=="disk"{print $1}\'); do echo "Name: $storage"; read type size rota tran < <(lsblk -dnro TYPE,SIZE,ROTA,TRAN "/dev/$storage"); rota_int=$(echo "$rota" | tr -d "[:space:]"); description="$([ $rota_int -eq 0 ] && echo SSD || echo HDD) - $tran"; echo -e "Type: $type\\nDiskSize: $size\\nDescription: $description"; smartctl_info=$(smartctl -i "/dev/$storage" 2>/dev/null); echo "$smartctl_info" | grep -E "Model Number|Serial Number|Firmware Version" | sed -e \'s/Model Number:/Model:/\' -e \'s/Serial Number:/SerialNumber:/\' -e \'s/Firmware Version:/Firmware:/\'; pci_line=$(echo "$smartctl_info" | grep "PCI Vendor/Subsystem ID"); if [[ -n "$pci_line" ]]; then pci_id=$(echo "$pci_line" | grep -Po \'0x[0-9a-fA-F]+\'); vendor_id=${pci_id#0x}; if [[ -f /usr/share/hwdata/pci.ids ]]; then manufacturer=$(grep -i "^$vendor_id " /usr/share/hwdata/pci.ids | head -n1 | cut -f2- -d\' \'); echo "Manufacturer: $manufacturer"; fi; fi; echo "---"; done',
            "options": {"multiple": False, "separator": "---"},
            "template": template,
        },
        {
            "name": "USB DEVICES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "lsusb -v",
            "options": {"multiple": False, "separator": "\\nBus"},
            "template": template,
        },
        {
            "name": "VIDEOS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'videos=($(lspci | grep -iE \'graphics|vga|video|display\' | cut -d \' \' -f1)); for slot in "${videos[@]}"; do info=$(lspci -vmm -s "$slot"); chipset=$(echo "$info" | grep \'^Class:\' | cut -f2-); vendor=$(echo "$info" | grep \'^Vendor:\' | cut -f2-); device=$(echo "$info" | grep \'^Device:\' | cut -f2-); name="$vendor $device"; memory=0; while IFS= read -r line; do if [[ $line =~ Memory.*\\(.*-bit,\\ prefetchable\\)\\ \\[size=([0-9]+)([GMK])\\] ]]; then size=${BASH_REMATCH[1]}; unit=${BASH_REMATCH[2]}; case $unit in G) bytes=$(( size * 1024 * 1024 * 1024 )) ;; M) bytes=$(( size * 1024 * 1024 )) ;; K) bytes=$(( size * 1024 )) ;; esac; memory=$(( memory + bytes )); fi; done < <(lspci -v -s "$slot" 2>/dev/null); memory_mb=$(( (memory + 524288) / 1048576 )); echo "Chipset: $chipset"; echo "Name: $name"; echo "Memory: ${memory_mb} MB"; echo "---"; done',
            "options": {"multiple": False, "separator": "---"},
            "template": template,
        },
        {
            "name": "LOCAL GROUPS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "cat /etc/group",
            "options": {"multiple": True, "separator": None},
            "template": template,
        },
        {
            "name": "REPOSITORY",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "apt-cache policy | grep -iE \"http(s)?://\" | awk '{print $2, $3}' | sort -u",
            "options": {"multiple": True, "separator": None},
            "template": template,
        },
        {
            "name": "SOFTWARES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'dpkg -l | awk \'NR>5 {print $2}\' | while read -r pkg; do install_date=$(stat -c %y "/var/lib/dpkg/info/${pkg}.list" 2>/dev/null | cut -d. -f1 || echo "unknown"); dpkg -s "$pkg" 2>/dev/null | awk -v pkg="$pkg" -v id="$install_date" \'BEGIN {name=pkg;publisher="";version="";comments="";size_kb=0;arch="";from="deb";major="";minor=""} /^Homepage[[:space:]]*:/ {publisher=substr($0,index($0,":")+2)} /^Version[[:space:]]*:/ {version=substr($0,index($0,":")+2); raw_version=version; sub(/^[0-9]+:/, "", raw_version); if(match(raw_version,/^[0-9]+(\\.[0-9]+)*/)){vernum=substr(raw_version,RSTART,RLENGTH); split(vernum, parts, "."); major=(parts[1]~/^[0-9]+$/)?parts[1]:""; if(length(parts)>1) minor=(parts[2]~/^[0-9]+$/)?parts[2]:""; if(length(parts)>2) patch=(parts[3]~/^[0-9]+$/)?parts[3]:"";} } /^Description[[:space:]]*:/ && !d {comments=substr($0,index($0,":")+2); d=1} /^Installed-Size[[:space:]]*:/ {size_kb=substr($0,index($0,":")+2)} /^Architecture[[:space:]]*:/ {arch=substr($0,index($0,":")+2)} END {size=size_kb*1024; printf("Name: %s\\nPublisher: %s\\nVersion: %s\\nComments: %s\\nFileSize: %d\\nInstallDate: %s\\nFrom: %s\\nArchitecture: %s\\n", name, publisher, version, comments, size, id, from, arch); if(major!="") printf("Major: %s\\n", major); if(minor!="") printf("Minor: %s\\n", minor); if(patch!="") printf("Patch: %s\\n", patch); printf("---\\n") }\'; done',
            "options": {"multiple": False, "separator": "---"},
            "template": template,
        },
        {
            "name": "BATTERIES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "upower -i $(upower -e | grep BAT)",
            "options": {"multiple": False, "separator": "native-path:"},
            "template": template,
        },
        {
            "name": "FIREWALL RULES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'sudo bash -c \'for bin in iptables ip6tables; do ver=$([ "$bin" = "iptables" ] && echo "IPv4" || echo "IPv6"); for chain in INPUT OUTPUT FORWARD; do while IFS= read -r line; do line=$(echo "$line" | sed "s/^[[:space:]]*//;s/[[:space:]]*$//"); [ -z "$line" ] && continue; read -r pkts bytes action proto opt in_if out_if source dest rest <<< "$line"; [ -z "$dest" ] && continue; [[ "${source,,}" == "source" ]] && continue; case $(echo "$proto" | tr -cd "0-9") in 1) p="ICMP";; 6) p="TCP";; 17) p="UDP";; 58) p="IPv6-ICMP";; *) p="$proto";; esac; comment=$(echo "$rest" | grep -oP "(?<=/\\* ).*?(?= \\*/)"); dst_port=$(echo "$rest" | grep -oP "dpts?:\\K[\\d:]+"); src_port=$(echo "$rest" | grep -oP "spts?:\\K[\\d:]+"); other=$(echo "$rest" | sed "s|/\\*.*\\*\\/||g;s/dpts\\?:[0-9:]* //g;s/spts\\?:[0-9:]* //g;s/^[[:space:]]*//;s/[[:space:]]*$//"); [ "$in_if" != "*" ] && [ -n "$in_if" ] && other="in=$in_if $other"; [ "$out_if" != "*" ] && [ -n "$out_if" ] && other="$other out=$out_if"; echo "DIRECTION=$chain SOURCE=$source SOURCE_PORT=$src_port DESTINATION=$dest DESTINATION_PORT=$dst_port ACTION=$action PROTOCOL=$p COMMENT=$comment OTHER=$other"; done < <($bin -L $chain -n -v 2>/dev/null | tail -n +3); done; done\'',
            "options": {"multiple": False, "separator": "DIRECTION="},
            "template": template,
        },
        {
            "name": "UPTIME",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "python3 -c \"import subprocess,datetime;u=open('/proc/uptime').read().split()[0];s=int(float(u));d=s//86400;h=(s%86400)//3600;m=(s%3600)//60;boot=subprocess.check_output('uptime -s',shell=True).decode().strip();print(f'DURATION={d:02d} days {h:02d} hours {m:02d} minutes\\nLOG_DATE={boot}')\"",
            "options": {"multiple": False, "separator": None},
            "template": template,
        },
        {
            "name": "SECURITY CERTIFICATE",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "for f in /etc/ssl/certs/*.pem /etc/ssl/certs/*.crt; do [ -f \"$f\" ] && echo \"NAME=$(basename $f) AUTHORITY=$(openssl x509 -in $f -noout -issuer 2>/dev/null | sed 's/issuer=//') DATESTART=$(openssl x509 -in $f -noout -startdate 2>/dev/null | sed 's/notBefore=//') EXPIRATION=$(openssl x509 -in $f -noout -enddate 2>/dev/null | sed 's/notAfter=//') \"; done",
            "options": {"multiple": False, "separator": "NAME"},
            "template": template,
        },
        {
            "name": "CRON TAB TASKS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "grep -rh --include=\"*\" -E \"^[^#]\" /etc/cron.d/ /etc/crontab /var/spool/cron/ /var/spool/cron/crontabs/ 2>/dev/null | grep -v \"^$\" | while read line; do echo \"$line\" | python3 -c \"import sys,re; l=sys.stdin.read().strip(); f=l.split(); is_sys=len(f)>=6 and not re.match(r'^[\\*0-9,\\-/]+$',f[5] if len(f)>5 else ''); m,h,dom,month,dow=(f[0],f[1],f[2],f[3],f[4]) if len(f)>=5 else ('','','','',''); user=f[5] if is_sys and len(f)>5 else ''; cmd=' '.join(f[6:]) if is_sys and len(f)>6 else ' '.join(f[5:]) if len(f)>5 else ''; print(f'MINUTE={m} HOUR={h} DOM={dom} MONTH={month} DOW={dow} USER={user} CRON={cmd}') if len(f)>=5 else None\"; done",
            "options": {"multiple": False, "separator": "MINUTE"},
            "template": template,
        },
        {
            "name": "RUNNING PROCESS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "ps aux | tail -n +2 | python3 -c \"import sys,datetime; months={'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06','Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'}; now=datetime.datetime.now(); [print('USERNAME='+f[0]+' PROCESSID='+f[1]+' CPUUSAGE='+f[2]+' PROCESSMEMORY='+f[3]+' VIRTUALMEMORY='+f[4]+' TTY='+f[6]+' STARTED='+(now.strftime('%Y-')+months.get(f[8][:3],'00')+'-'+f[8][3:]+' '+f[9] if f[8][:3] in months else now.strftime('%Y-%m-%d')+' '+f[8])+' COMMANDLINE='+' '.join(f[10:])) for line in sys.stdin for f in [line.split()] if len(f)>=11]\"",
            "options": {"multiple": False, "separator": "USERNAME"},
            "template": template,
        },
        {
            "name": "VIRTUAL MACHINES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": "(for u in $(cut -d: -f1 /etc/passwd); do sudo -u $u bash -c 'VBoxManage list vms; virsh --connect qemu:///session list --all --name'; done; virsh --connect qemu:///system list --all --name) 2>/dev/null | grep -v '^$'",
            "options": {"multiple": True, "separator": None},
            "template": template,
        },
    ]

    for section in sections:
        try:
            Section.objects.create(**section)
        except Exception as e:
            print(e)


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0011_windows_extended"),
        ("template", "0005_linux_extended_debian"),
    ]

    operations = [
        migrations.RunPython(create_linux_extended_debian_sections),
    ]
