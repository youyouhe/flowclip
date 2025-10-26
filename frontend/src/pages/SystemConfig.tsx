import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Form, Input, Button, Spin, Alert, Typography, Divider, Collapse, Tag, Select, Upload, message, Tabs, Switch, Radio } from 'antd';
import { systemConfigAPI, capcutAPI, jianyingAPI, asrAPI, llmAPI } from '../services/api';
import { useAuth } from '../components/AuthProvider';
import { UploadOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { AxiosResponse } from 'axios';

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
  const [asrTestFile, setAsrTestFile] = useState<File | null>(null);
  const [asrTesting, setAsrTesting] = useState(false);
  const [asrTestResult, setAsrTestResult] = useState<string | null>(null);
  const [llmModels, setLlmModels] = useState<Array<{id: string, name: string}>>([]);
  const { user } = useAuth();

  // 配置项显示名称映射
  const getConfigDisplayName = (key: string) => {
    const displayNames: Record<string, string> = {
      // TUS配置显示名称
      'tus_api_url': 'TUS API服务地址',
      'tus_upload_url': 'TUS上传服务地址',
      'tus_file_size_threshold_mb': 'TUS文件大小阈值(MB)',
      'tus_enable_routing': '启用TUS路由',
      'tus_max_retries': 'TUS最大重试次数',
      'tus_timeout_seconds': 'TUS超时时间(秒)',

      // 其他配置的显示名称可以继续添加
      'asr_service_url': 'ASR服务地址',
      'openrouter_api_key': 'OpenRouter API密钥',
      'capcut_api_url': 'CapCut API地址',
      'jianying_api_url': 'Jianying API地址',
      'jianying_draft_folder': 'Jianying默认草稿文件夹',
    };

    return displayNames[key] || key;
  };

  // 配置项描述映射
  const getConfigDescription = (key: string) => {
    const descriptions: Record<string, string> = {
      // TUS配置描述
      'tus_api_url': 'TUS ASR API服务的完整URL地址，用于创建ASR任务和下载结果',
      'tus_upload_url': 'TUS文件上传服务的URL地址，用于上传音频文件',
      'tus_file_size_threshold_mb': '文件大小阈值(MB)，超过此大小的文件将使用TUS协议',
      'tus_enable_routing': '是否启用基于文件大小的TUS路由功能',
      'tus_max_retries': 'TUS操作失败时的最大重试次数',
      'tus_timeout_seconds': 'TUS操作的超时时间(秒)',

      // 其他配置描述
      'asr_service_url': 'ASR服务的URL地址，用于音频转文字处理',
      'openrouter_api_key': 'OpenRouter API密钥，用于访问LLM服务',
      'capcut_api_url': 'CapCut API服务的URL地址，用于视频编辑功能',
      'jianying_api_url': 'Jianying API服务的URL地址，用于剪映视频编辑功能',
      'jianying_draft_folder': 'Jianying导出的默认草稿保存文件夹路径，支持Windows和Unix路径格式',
    };

    return descriptions[key] || '';
  };

  useEffect(() => {
    console.log('SystemConfig组件已加载');
    fetchSystemConfigs();
  }, []);

  // 获取LLM模型列表
  useEffect(() => {
    const fetchLlmModels = async () => {
      try {
        const response = await llmAPI.getAvailableModels();
        if (response.data && response.data.models) {
          setLlmModels(response.data.models);
        }
      } catch (err: any) {
        console.error('获取LLM模型列表失败:', err);
        // 如果获取失败，使用默认模型列表
        setLlmModels([
          { id: 'google/gemini-2.5-flash', name: 'Google: Gemini 2.5 Flash' },
          { id: 'google/gemini-2.5-flash-lite', name: 'Google: Gemini 2.5 Flash Lite' },
          { id: 'openai/gpt-4', name: 'OpenAI: GPT-4' },
          { id: 'openai/gpt-3.5-turbo', name: 'OpenAI: GPT-3.5 Turbo' }
        ]);
      }
    };

    fetchLlmModels();
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
      response.data.forEach((config: { key: string | number; value: string; }) => {
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

  const testAsrService = async () => {
    if (!asrTestFile) {
      message.error('请先选择一个音频文件');
      return;
    }

    try {
      setAsrTesting(true);
      setAsrTestResult(null);

      // 获取当前表单中的ASR相关配置
      const formValues = form.getFieldsValue();
      const asrModelType = formValues.asr_model_type || 'whisper';
      const asrApiKey = formValues.asr_api_key;

      // 检查是否配置了ASR API密钥
      if (!asrApiKey) {
        message.warning('未配置ASR API密钥，测试可能会失败');
      }

      // 调用后端代理API进行测试，传递API密钥
      const response = await asrAPI.testAsrService(asrTestFile, asrModelType, asrApiKey);

      // 处理响应结果
      if (response.data.success) {
        setAsrTestResult(response.data.result || 'ASR服务测试成功，但未返回结果');
        message.success('ASR服务测试成功');
      } else {
        throw new Error(response.data.error || 'ASR服务测试失败');
      }
    } catch (err: any) {
      console.error('ASR服务测试失败:', err);
      const errorMsg = err.response?.data?.detail || err.response?.data?.error || err.message || 'ASR服务测试失败';
      message.error(`ASR服务测试失败: ${errorMsg}`);
      setAsrTestResult(`错误: ${errorMsg}`);
    } finally {
      setAsrTesting(false);
    }
  };

  const checkServiceStatus = async (serviceName: string) => {
    console.log(`开始检查服务状态: ${serviceName}`);
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

      // 对于CapCut和Jianying服务，使用专门的API检查
      let response: AxiosResponse<any, any, {}>;
      if (serviceName === 'capcut') {
        response = await capcutAPI.getStatus();
        setServiceStatus(prev => ({
          ...prev,
          [serviceName]: {
            service: serviceName,
            status: response.data.status === 'online' ? 'online' : 'offline',
            message: response.data.status === 'online' ? 'CapCut服务正常' : 'CapCut服务离线'
          }
        }));
      } else if (serviceName === 'jianying') {
        response = await jianyingAPI.getStatus();
        setServiceStatus(prev => ({
          ...prev,
          [serviceName]: {
            service: serviceName,
            status: response.data.status === 'online' ? 'online' : 'offline',
            message: response.data.status === 'online' ? 'Jianying服务正常' : 'Jianying服务离线'
          }
        }));
      } else {
        response = await systemConfigAPI.checkServiceStatus(serviceName);
        setServiceStatus(prev => ({
          ...prev,
          [serviceName]: response.data
        }));
      }
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
    
    // 对"其他服务配置"类别中的ASR相关配置项进行自定义排序
    // 确保asr_model_type在asr_service_url之前显示
    if (groups['其他服务配置']) {
      groups['其他服务配置'].sort((a, b) => {
        // 如果是asr_model_type，排在asr_service_url前面
        if (a.key === 'asr_model_type' && b.key === 'asr_service_url') {
          return -1;
        }
        // 如果是asr_service_url，排在asr_model_type后面
        if (a.key === 'asr_service_url' && b.key === 'asr_model_type') {
          return 1;
        }
        // 其他情况保持原有顺序
        return 0;
      });
    }
    
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
  'capcut': '其他服务配置',
  'jianying': '其他服务配置',
  'llm': 'LLM配置'
};

// 定义服务显示名称
const serviceDisplayNames: Record<string, string> = {
  'mysql': 'MySQL',
  'redis': 'Redis',
  'minio': 'MinIO',
  'asr': 'ASR',
  'capcut': 'CapCut',
  'jianying': 'Jianying',
  'llm': 'LLM'
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
        <Collapse
          defaultActiveKey={Object.keys(groupedConfigs)}
          items={Object.entries(groupedConfigs).map(([category, configs]) => {
            // 检查是否需要添加健康检查按钮
            const service = Object.keys(serviceCategoryMap).find(
              key => serviceCategoryMap[key] === category
            );

            return {
              key: category,
              label: (
                <span>
                  {category}
                  {category === '其他服务配置' && (
                    <span className="ml-4">
                      {/* 显式列出所有相关服务的状态检查按钮 */}
                      <span key="asr-status" className="mr-4">
                        ASR服务状态: <ServiceStatusTag serviceName="asr" />
                      </span>
                      <span key="capcut-status" className="mr-4">
                        CapCut服务状态: <ServiceStatusTag serviceName="capcut" />
                      </span>
                      <span className="mr-4">
                        Jianying测试按钮: <Button size="small">测试</Button>
                      </span>
                      <span key="jianying-status" className="mr-4">
                        {serviceDisplayNames['jianying']}服务状态: <ServiceStatusTag serviceName="jianying" />
                      </span>
                      <span key="llm-status" className="mr-4">
                        LLM服务状态: <ServiceStatusTag serviceName="llm" />
                      </span>
                    </span>
                  )}
                  {service && category !== '其他服务配置' && (
                    <span className="ml-4">
                      {serviceDisplayNames[service] || service}服务状态: <ServiceStatusTag serviceName={service} />
                    </span>
                  )}

                  </span>
              ),
              children: (
                <>
                  {(category === '其他服务配置' || category === 'LLM配置') && (
                    <div style={{ marginBottom: '24px', padding: '16px', backgroundColor: '#f0f2f5', borderRadius: '8px' }}>
                      {category === '其他服务配置' && (
                        <Title level={4} style={{ marginTop: 0, marginBottom: '16px' }}>
                          <PlayCircleOutlined /> ASR服务测试
                        </Title>
                      )}
                      {category === 'LLM配置' && (
                        <>
                          <Title level={4} style={{ marginTop: 0, marginBottom: '16px' }}>
                            <PlayCircleOutlined /> LLM服务状态
                          </Title>
                          <Row gutter={[16, 16]}>
                            <Col span={24}>
                              <Text>LLM服务配置状态将在此显示</Text>
                            </Col>
                          </Row>
                        </>
                      )}
                      {category === '其他服务配置' && (
                        <>
                          <Row gutter={[16, 16]}>
                            <Col span={24}>
                              <Text strong>上传音频文件进行测试:</Text>
                            </Col>
                            <Col span={12}>
                          <Upload
                            accept=".wav,.mp3,.flac,.aac,.ogg,.webm,.m4a,.opus,audio/*"
                            beforeUpload={(file) => {
                              const allowedTypes = [
                                'audio/wav',
                                'audio/x-wav',
                                'audio/mp3',
                                'audio/mpeg',
                                'audio/flac',
                                'audio/aac',
                                'audio/ogg',
                                'audio/webm',
                                'audio/mp4',
                                'audio/x-m4a',
                                'audio/opus'
                              ];

                              const isAllowedType = allowedTypes.includes(file.type) ||
                                file.name.toLowerCase().match(/\.(wav|mp3|flac|aac|ogg|webm|m4a|opus)$/);

                              if (!isAllowedType) {
                                message.error('请上传音频文件 (WAV, MP3, FLAC, AAC, OGG, WEBM, M4A, OPUS)');
                                return false;
                              }

                              // 检查文件大小 (限制为5MB)
                              const maxSize = 5 * 1024 * 1024; // 5MB
                              if (file.size > maxSize) {
                                message.error('文件大小不能超过5MB');
                                return false;
                              }

                              setAsrTestFile(file);
                              return false;
                            }}
                            maxCount={1}
                            fileList={asrTestFile ? [{ uid: '-1', name: asrTestFile.name, status: 'done' }] : []}
                            onRemove={() => setAsrTestFile(null)}
                          >
                            <Button icon={<UploadOutlined />}>选择音频文件</Button>
                          </Upload>
                          <Text type="secondary" style={{ display: 'block', marginTop: '8px' }}>
                            支持格式: WAV, MP3, FLAC, AAC, OGG, WEBM, M4A, OPUS (最大5MB)
                          </Text>
                        </Col>
                        <Col span={12}>
                          <Button
                            type="primary"
                            icon={<PlayCircleOutlined />}
                            onClick={testAsrService}
                            loading={asrTesting}
                            disabled={!asrTestFile}
                          >
                            测试ASR服务
                          </Button>
                        </Col>
                        {asrTestResult && (
                          <Col span={24}>
                            <Text strong>测试结果:</Text>
                            <div style={{
                              marginTop: '8px',
                              padding: '12px',
                              backgroundColor: '#fff',
                              border: '1px solid #d9d9d9',
                              borderRadius: '4px',
                              maxHeight: '300px',
                              overflow: 'auto',
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'monospace',
                              fontSize: '12px'
                            }}>
                              {asrTestResult}
                            </div>
                          </Col>
                        )}
                      </Row>
                        </>
                      )}
                    </div>
                  )}
                  <Row gutter={16}>
                    {configs.map(config => (
                      <Col span={24} key={config.key}>
                        <Form.Item
                          label={
                            <span>
                              {getConfigDisplayName(config.key)}
                              {config.default && (
                                <Text type="secondary" className="ml-2">
                                  (默认: {config.key === 'llm_system_prompt' && config.default.length > 200 ? config.default.substring(0, 200) + '...' : config.default})
                                </Text>
                              )}
                            </span>
                          }
                          help={config.description || getConfigDescription(config.key)}
                        >
                          {config.category === '数据库配置' ? (
                            // 数据库配置设为只读
                            <Input
                              value={config.value}
                              readOnly
                              disabled
                            />
                          ) : config.key === 'asr_model_type' ? (
                            // ASR模型类型选择下拉框
                            <Form.Item name={config.key} noStyle>
                              <Select
                                placeholder="请选择ASR模型类型"
                                onChange={(value) => form.setFieldsValue({ [config.key]: value })}
                              >
                                <Select.Option value="whisper">Whisper模型</Select.Option>
                                <Select.Option value="sense">Sense模型</Select.Option>
                              </Select>
                            </Form.Item>
                          ) : config.key === 'capcut_api_key' ? (
                            // CapCut API密钥输入框
                            <Form.Item name={config.key} noStyle>
                              <Input.Password
                                placeholder={config.default || "请输入CapCut API密钥"}
                                visibilityToggle={true}
                              />
                            </Form.Item>
                          ) : config.key === 'jianying_api_key' ? (
                            // Jianying API密钥输入框
                            <Form.Item name={config.key} noStyle>
                              <Input.Password
                                placeholder={config.default || "请输入Jianying API密钥"}
                                visibilityToggle={true}
                              />
                            </Form.Item>
                          ) : config.key === 'llm_model_type' ? (
                            // LLM模型类型支持手动输入的输入框
                            <Form.Item name={config.key} noStyle>
                              <Input
                                placeholder={config.default || '请输入LLM模型类型，如 google/gemini-2.5-flash'}
                              />
                            </Form.Item>
                          ) : config.key === 'llm_system_prompt' ? (
                            // LLM系统提示词使用文本区域
                            <Form.Item name={config.key} noStyle>
                              <Input.TextArea
                                rows={8}
                                placeholder={config.default || `请输入${config.key}`}
                                showCount
                                maxLength={5000}
                              />
                            </Form.Item>
                          ) : config.key === 'llm_base_url' ? (
                            // LLM基础URL使用URL输入框
                            <Form.Item name={config.key} noStyle>
                              <Input
                                placeholder={config.default || `请输入${config.key}`}
                                addonBefore="https://"
                              />
                            </Form.Item>
                          ) : config.key === 'llm_temperature' || config.key === 'llm_max_tokens' ? (
                            // LLM数值参数使用数字输入框
                            <Form.Item name={config.key} noStyle>
                              <Input
                                type="number"
                                placeholder={config.default || `请输入${config.key}`}
                                step={config.key === 'llm_temperature' ? "0.1" : "1"}
                                min={config.key === 'llm_temperature' ? "0" : "1"}
                                max={config.key === 'llm_temperature' ? "1" : "100000"}
                              />
                            </Form.Item>
                          ) : config.key.includes('password') || config.key.includes('secret') || config.key.includes('key') ? (
                            <Form.Item name={config.key} noStyle>
                              <Input.Password
                                placeholder={config.default || `请输入${config.key}`}
                                visibilityToggle={true}
                              />
                            </Form.Item>
                          ) : config.key.includes('use_') && config.key.includes('callback') ? (
                            // 跳过已移除的回调相关配置
                            null
                          ) : (
                            <Form.Item name={config.key} noStyle>
                              <Input
                                placeholder={config.default || `请输入${config.key}`}
                              />
                            </Form.Item>
                          )}
                        </Form.Item>
                      </Col>
                    ))}
                  </Row>
                </>
              )
            };
          })}
        />

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