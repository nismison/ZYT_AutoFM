import ipaddress

import psutil


def get_real_lan_ip():
    """获取真实内网 IPv4 地址，排除虚拟网卡和回环地址"""
    for iface, info_list in psutil.net_if_addrs().items():
        for addr in info_list:
            if addr.family.name == 'AF_INET':
                ip = ipaddress.ip_address(addr.address)
                # 排除环回、本地链路、测试网
                if ip.is_private and not ip.is_link_local and not ip.is_loopback and not str(ip).startswith("198.18."):
                    return str(ip)
    return "127.0.0.1"


if __name__ == "__main__":
    print(get_real_lan_ip())
