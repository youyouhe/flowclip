# WireGuard VPN 部署指南

## 概述
使用WireGuard构建私有VPN网络，解决ngrok转发导致的timeout和SSL问题，让所有服务在安全的内网中通信。

## 网络规划
- VPN网段: `10.8.0.0/24`
- WireGuard服务器: `10.8.0.1`
- Backend服务: `10.8.0.2`
- ASR服务: `10.8.0.3`

## 部署步骤

### 1. WireGuard服务器配置

#### 1.1 安装WireGuard
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y wireguard

# 启用IP转发
echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-wireguard.conf
echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-wireguard.conf
sudo sysctl -p /etc/sysctl.d/99-wireguard.conf
```

#### 1.2 生成服务器密钥
```bash
cd /etc/wireguard/

# 生成服务器私钥和公钥
wg genkey | tee privatekey | wg pubkey > publickey

# 查看生成的密钥
echo "服务器私钥:" $(cat privatekey)
echo "服务器公钥:" $(cat publickey)
```

#### 1.3 创建服务器配置文件
```bash
# 创建配置文件 /etc/wireguard/wg0.conf
cat > /etc/wireguard/wg0.conf << 'EOF'
[Interface]
Address = 10.8.0.1/24
PrivateKey = <服务器私钥>
ListenPort = 51820

# 启用NAT
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer] # Backend服务
PublicKey = <Backend公钥>
AllowedIPs = 10.8.0.2/32

[Peer] # ASR服务
PublicKey = <ASR服务公钥>
AllowedIPs = 10.8.0.3/32
EOF
```

#### 1.4 启动WireGuard服务器
```bash
# 启动服务
sudo wg-quick up wg0

# 设置开机启动
sudo systemctl enable wg-quick@wg0

# 检查状态
sudo wg show
sudo ip addr show wg0
```

### 2. Backend服务配置

#### 2.1 在Backend服务器上安装WireGuard
```bash
sudo apt update
sudo apt install -y wireguard
```

#### 2.2 生成Backend客户端密钥
```bash
cd /etc/wireguard/

# 生成客户端私钥和公钥
wg genkey | tee backend_privatekey | wg pubkey > backend_publickey

echo "Backend私钥:" $(cat backend_privatekey)
echo "Backend公钥:" $(cat backend_publickey)
```

#### 2.3 创建Backend客户端配置
```bash
cat > /etc/wireguard/wg0.conf << 'EOF'
[Interface]
PrivateKey = <Backend私钥>
Address = 10.8.0.2/24

[Peer] # WireGuard服务器
PublicKey = <服务器公钥>
Endpoint = <服务器公网IP>:51820
AllowedIPs = 10.8.0.0/24
PersistentKeepalive = 25
EOF
```

#### 2.4 启动Backend客户端
```bash
# 启动VPN
sudo wg-quick up wg0
sudo systemctl enable wg-quick@wg0

# 测试连接
ping 10.8.0.1
```

### 3. ASR服务配置

#### 3.1 在ASR服务器上安装WireGuard
```bash
sudo apt update
sudo apt install -y wireguard
```

#### 3.2 生成ASR客户端密钥
```bash
cd /etc/wireguard/

# 生成客户端私钥和公钥
wg genkey | tee asr_privatekey | wg pubkey > asr_publickey

echo "ASR私钥:" $(cat asr_privatekey)
echo "ASR公钥:" $(cat asr_publickey)
```

#### 3.3 创建ASR客户端配置
```bash
cat > /etc/wireguard/wg0.conf << 'EOF'
[Interface]
PrivateKey = <ASR私钥>
Address = 10.8.0.3/24

[Peer] # WireGuard服务器
PublicKey = <服务器公钥>
Endpoint = <服务器公网IP>:51820
AllowedIPs = 10.8.0.0/24
PersistentKeepalive = 25
EOF
```

#### 3.4 启动ASR客户端
```bash
# 启动VPN
sudo wg-quick up wg0
sudo systemctl enable wg-quick@wg0

# 测试连接
ping 10.8.0.1
ping 10.8.0.2
```

### 4. 防火墙配置

#### 4.1 在WireGuard服务器上配置防火墙
```bash
# 开放UDP 51820端口
sudo ufw allow 51820/udp

# 如果使用UFW，确保允许转发
sudo ufw route allow in on wg0 out on eth0
sudo ufw route allow in on eth0 out on wg0
```

#### 4.2 检查NAT和转发规则
```bash
# 检查iptables规则
sudo iptables -t nat -L -n -v
sudo iptables -L FORWARD -n -v
```

### 5. 更新应用配置

#### 5.1 更新数据库中的ASR服务URL
```python
import sys
sys.path.append('.')
from app.core.database import get_sync_db
from app.models.system_config import SystemConfig

with get_sync_db() as db:
    # 更新ASR服务URL为VPN内网地址
    asr_config = db.query(SystemConfig).filter(SystemConfig.config_key == 'asr_service_url').first()
    if asr_config:
        asr_config.config_value = 'http://10.8.0.3:5001'
    else:
        asr_config = SystemConfig(
            config_key='asr_service_url',
            config_value='http://10.8.0.3:5001',
            config_type='string',
            description='ASR服务VPN内网地址'
        )
        db.add(asr_config)

    db.commit()
    print('ASR服务URL已更新为VPN内网地址')
```

#### 5.2 重启Backend服务以应用新配置
```bash
# 重启Backend服务
sudo systemctl restart flowclip-backend
sudo systemctl restart flowclip-celery
```

### 6. 测试VPN连接

#### 6.1 测试网络连通性
```bash
# 在Backend服务器上测试
ping 10.8.0.3        # 测试到ASR服务的连通性
curl http://10.8.0.3:5001/health  # 测试ASR服务健康检查

# 在ASR服务器上测试
ping 10.8.0.2        # 测试到Backend服务的连通性
```

#### 6.2 测试完整流程
```bash
# 在Backend服务器上测试大文件处理
python -c "
import requests
import time

# 测试ASR服务连接
start_time = time.time()
try:
    response = requests.get('http://10.8.0.3:5001/health', timeout=30)
    print(f'ASR服务连接成功: {response.status_code}')
    print(f'响应时间: {time.time() - start_time:.2f}秒')
except Exception as e:
    print(f'连接失败: {e}')
"
```

### 7. 监控和维护

#### 7.1 WireGuard状态监控
```bash
# 查看VPN连接状态
sudo wg show

# 查看VPN接口状态
ip addr show wg0

# 查看路由表
ip route show

# 查看连接统计
sudo wg show all dump
```

#### 7.2 日志查看
```bash
# 查看WireGuard日志
journalctl -u wg-quick@wg0 -f

# 查看系统网络日志
journalctl -u networking -f
```

### 8. 故障排除

#### 8.1 常见问题
1. **连接超时** - 检查防火墙和端口转发
2. **密钥配置错误** - 重新生成和配置密钥
3. **路由问题** - 检查AllowedIPs配置
4. **NAT问题** - 检查iptables规则

#### 8.2 重置配置
```bash
# 停止WireGuard
sudo wg-quick down wg0

# 清理配置
sudo rm /etc/wireguard/wg0.conf

# 重新配置 (从头开始)
```

### 9. 安全建议

#### 9.1 密钥管理
- 定期更换密钥
- 妥善保存私钥文件
- 限制配置文件权限

#### 9.2 网络安全
- 使用强密码
- 限制访问IP
- 定期更新系统

#### 9.3 备份方案
- 备份配置文件
- 记录密钥信息
- 准备恢复流程

## 部署验证清单

- [ ] WireGuard服务器安装完成
- [ ] 所有客户端密钥已生成
- [ ] VPN连接建立成功
- [ ] 内网地址ping测试通过
- [ ] ASR服务健康检查正常
- [ ] 应用配置已更新
- [ ] 大文件处理测试通过
- [ ] 防火墙规则配置正确
- [ ] 开机启动已设置
- [ ] 监控和日志正常

## 预期效果

部署完成后：
- 所有服务通过VPN内网通信
- 消除ngrok转发的SSL和timeout问题
- 提高连接稳定性和传输速度
- 增强网络安全性和隐私保护
- 支持大文件稳定传输