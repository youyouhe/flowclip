import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Form, Input, Button, Spin, Alert, Typography, Divider, Collapse, Tag } from 'antd';
import { systemConfigAPI } from '../services/api';
import { useAuth } from '../components/AuthProvider';

const { Title, Text } = Typography;
const { Panel } = Collapse;

interface ConfigItem {
  key: string;
  value: string;
  description: string;
  category: string;
  default: string;
}

interface ServiceStatus {
  service: string;
  status: 'online' | 'offline' | 'checking';
  message: string;
}

const SystemConfig: React.FC = () => {
  const [form] = Form.useForm();
  const [configs, setConfigs] = useState<ConfigItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [serviceStatus, setServiceStatus] = useState<Record<string, ServiceStatus>>({});
  const { user } = useAuth();

  useEffect(() => {
    fetchSystemConfigs();
  }, []);

  // 页面加载时自动检查所有服务状态
  useEffect(() => {
    if (configs.length > 0 && Object.keys(serviceStatus).length === 0) {
      Object.keys(serviceCategoryMap).forEach(serviceName => {
        // 延迟检查，避免同时发起过多请求
        setTimeout(() => {
          checkServiceStatus(serviceName);
        }, 100 * Object.keys(serviceCategoryMap).indexOf(serviceName));
      });
    }
  }, [configs]);

  const fetchSystemConfigs = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await systemConfigAPI.getSystemConfigs();
      setConfigs(response.data);
      
      // 设置表单初始值
      const initialValues: Record<string, string> = {};
      response.data.forEach(config => {
        initialValues[config.key] = config.value;
      });
      form.setFieldsValue(initialValues);
    } catch (err: any) {
      console.error('获取系统配置失败:', err);
      setError(err.response?.data?.detail || '获取系统配置失败');
    } finally {
      setLoading(false);
    }
  };

  const checkServiceStatus = async (serviceName: string) => {
    try {
      // 设置为检查中状态
      setServiceStatus(prev => ({
        ...prev,
        [serviceName]: {
          service: serviceName,
          status: 'checking',
          message: '检查中...'
        }
      }));
      
      const response = await systemConfigAPI.checkServiceStatus(serviceName);
      setServiceStatus(prev => ({
        ...prev,
        [serviceName]: response.data
      }));
    } catch (err: any) {
      console.error(`${serviceName}服务检查失败:`, err);
      setServiceStatus(prev => ({
        ...prev,
        [serviceName]: {
          service: serviceName,
          status: 'offline',
          message: err.response?.data?.detail || `${serviceName}服务检查失败`
        }
      }));
    }
  };

  const onFinish = async (values: Record<string, string>) => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      
      // 构造更新数据
      const updateData = Object.keys(values).map(key => {
        const config = configs.find(c => c.key === key);
        return {
          key,
          value: values[key],
          description: config?.description || '',
          category: config?.category || ''
        };
      });
      
      await systemConfigAPI.updateSystemConfigs(updateData);
      setSuccess('配置保存成功');
      
      // 重新获取配置以确保同步
      await fetchSystemConfigs();
      
      // 重新检查所有服务状态，因为配置可能已更改
      Object.keys(serviceCategoryMap).forEach(serviceName => {
        setTimeout(() => {
          checkServiceStatus(serviceName);
        }, 500 * Object.keys(serviceCategoryMap).indexOf(serviceName));
      });
    } catch (err: any) {
      console.error('保存配置失败:', err);
      setError(err.response?.data?.detail || '保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  // 按类别分组配置项
  const groupConfigsByCategory = () => {
    const groups: Record<string, ConfigItem[]> = {};
    configs.forEach(config => {
      if (!groups[config.category]) {
        groups[config.category] = [];
      }
      groups[config.category].push(config);
    });
    return groups;
  };

  const groupedConfigs = groupConfigsByCategory();

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Alert
          message="错误"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={fetchSystemConfigs}>
              重试
            </Button>
          }
        />
      </div>
    );
  }

  // 移除了超级管理员检查，所有用户都可以访问系统配置页面

  // 定义服务与类别的映射关系
const serviceCategoryMap: Record<string, string> = {
  'mysql': '数据库配置',
  'redis': 'Redis配置',
  'minio': 'MinIO配置',
  'asr': '其他服务配置',
  'capcut': '其他服务配置'
};

// 定义服务显示名称
const serviceDisplayNames: Record<string, string> = {
  'mysql': 'MySQL',
  'redis': 'Redis',
  'minio': 'MinIO',
  'asr': 'ASR',
  'capcut': 'CapCut'
};

// 获取服务状态显示组件
const ServiceStatusTag = ({ serviceName }: { serviceName: string }) => {
  const status = serviceStatus[serviceName];
  const displayName = serviceDisplayNames[serviceName] || serviceName;
  
  if (!status) {
    return (
      <Button 
        size="small" 
        onClick={() => checkServiceStatus(serviceName)}
        className="ml-2"
      >
        检查
      </Button>
    );
  }
  
  const statusConfig = {
    online: { color: 'success', text: '在线' },
    offline: { color: 'error', text: '离线' },
    checking: { color: 'processing', text: '检查中' }
  };
  
  const config = statusConfig[status.status] || statusConfig.checking;
  
  return (
    <span>
      <Tag color={config.color}>{config.text}</Tag>
      <Button 
        size="small" 
        onClick={() => checkServiceStatus(serviceName)}
        className="ml-2"
      >
        刷新
      </Button>
      {status.message && (
        <Text type="secondary" className="ml-2" style={{ fontSize: '12px' }}>
          {status.message}
        </Text>
      )}
    </span>
  );
};

return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={2}>系统配置</Title>
      </div>

      {error && (
        <Alert
          message="错误"
          description={error}
          type="error"
          showIcon
          className="mb-6"
        />
      )}

      {success && (
        <Alert
          message="成功"
          description={success}
          type="success"
          showIcon
          className="mb-6"
        />
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        autoComplete="off"
      >
        <Collapse defaultActiveKey={Object.keys(groupedConfigs)}>
          {Object.entries(groupedConfigs).map(([category, configs]) => {
            // 检查是否需要添加健康检查按钮
            const service = Object.keys(serviceCategoryMap).find(
              key => serviceCategoryMap[key] === category
            );
            
            return (
              <Panel 
                header={
                  <span>
                    {category}
                    {category === '其他服务配置' && (
                      <span className="ml-4">
                        {Object.keys(serviceCategoryMap).filter(key => serviceCategoryMap[key] === category).map(serviceKey => (
                          <span key={serviceKey} className="mr-4">
                            {serviceDisplayNames[serviceKey] || serviceKey}服务状态: <ServiceStatusTag serviceName={serviceKey} />
                          </span>
                        ))}
                      </span>
                    )}
                    {service && category !== '其他服务配置' && (
                      <span className="ml-4">
                        {serviceDisplayNames[service] || service}服务状态: <ServiceStatusTag serviceName={service} />
                      </span>
                    )}
                  </span>
                } 
                key={category}
              >
                <Row gutter={16}>
                  {configs.map(config => (
                    <Col span={24} key={config.key}>
                      <Form.Item
                        label={
                          <span>
                            {config.key} 
                            {config.default && (
                              <Text type="secondary" className="ml-2">
                                (默认: {config.default})
                              </Text>
                            )}
                          </span>
                        }
                        name={config.key}
                        help={config.description}
                      >
                        {config.category === '数据库配置' ? (
                          // 数据库配置设为只读
                          <Input 
                            value={config.value}
                            readOnly
                            disabled
                          />
                        ) : config.key.includes('password') || config.key.includes('secret') || config.key.includes('key') ? (
                          <Input.Password 
                            placeholder={config.default || `请输入${config.key}`}
                            visibilityToggle={true}
                          />
                        ) : (
                          <Input 
                            placeholder={config.default || `请输入${config.key}`}
                          />
                        )}
                      </Form.Item>
                    </Col>
                  ))}
                </Row>
              </Panel>
            );
          })}
        </Collapse>

        <Divider />

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            保存配置
          </Button>
          <Button className="ml-4" onClick={fetchSystemConfigs}>
            取消
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
};

export default SystemConfig;