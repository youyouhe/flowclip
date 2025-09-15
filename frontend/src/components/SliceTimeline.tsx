import React, { useMemo, useState, useEffect } from 'react';
import Timeline, { TimelineHeaders, SidebarHeader, DateHeader } from 'react-calendar-timeline';
import moment from 'moment';
import { Card, Typography, Alert, Spin, Space, Modal, Button, Tag, Tooltip } from 'antd';
import { FullscreenOutlined, InfoCircleOutlined } from '@ant-design/icons';
import 'react-calendar-timeline/lib/Timeline.css';

const { Title, Text, Paragraph } = Typography;

const formatTime = (seconds: number) => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

interface TimelineItem {
  id: number;
  group: number;
  title: string;
  start_time: number;
  end_time: number;
  canMove: boolean;
  canResize: boolean;
  canChangeGroup: boolean;
  itemProps: {
    style: React.CSSProperties;
  };
  type: 'slice' | 'subslice';
  originalData: any;
}

interface Group {
  id: number;
  title: string;
  rightTitle?: string;
  stackItems?: boolean;
}

interface SliceTimelineProps {
  slices: any[];
  loading?: boolean;
  selectedVideo: number | null;
}

const SliceTimeline: React.FC<SliceTimelineProps> = ({ 
  slices, 
  loading = false, 
  selectedVideo 
}) => {
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedTimelineItem, setSelectedTimelineItem] = useState<TimelineItem | null>(null);
  const [itemModalVisible, setItemModalVisible] = useState(false);
  const [visibleTimeStart, setVisibleTimeStart] = useState<number>(0);
  const [visibleTimeEnd, setVisibleTimeEnd] = useState<number>(0);

  const timelineItems = useMemo(() => {
    if (!slices || slices.length === 0) return [];
    
    const items: TimelineItem[] = [];
    let itemIdCounter = 1;

    console.log('SliceTimeline - processing slices:', slices);

    slices.forEach((slice, sliceIndex) => {
      if (slice.start_time === undefined || slice.end_time === undefined) {
        console.warn(`Slice ${slice.id} missing time data, skipping`);
        return;
      }

      // Convert to milliseconds for Timeline
      const startTime = slice.start_time * 1000;
      const endTime = slice.end_time * 1000;

      // Main slice item
      items.push({
        id: itemIdCounter++,
        group: sliceIndex + 1,
        title: slice.cover_title || slice.title || `切片 ${sliceIndex + 1}`,
        start_time: startTime,
        end_time: endTime,
        canMove: false,
        canResize: false,
        canChangeGroup: false,
        itemProps: {
          style: {
            background: '#1890ff',
            color: 'white',
            borderRadius: '6px',
            border: '2px solid #1890ff',
            boxShadow: '0 2px 8px rgba(24, 144, 255, 0.3)',
            fontWeight: 'bold',
            fontSize: '12px',
            padding: '4px 8px'
          }
        },
        type: 'slice',
        originalData: slice
      });

      // Process sub-slices
      if (slice.sub_slices && slice.sub_slices.length > 0) {
        slice.sub_slices.forEach((subSlice: any, subIndex: number) => {
          if (subSlice.start_time === undefined || subSlice.end_time === undefined) {
            console.warn(`SubSlice ${subSlice.id} missing time data, skipping`);
            return;
          }

          const subStartTime = subSlice.start_time * 1000;
          const subEndTime = subSlice.end_time * 1000;

          items.push({
            id: itemIdCounter++,
            group: sliceIndex + 1,
            title: subSlice.cover_title || `子切片 ${subIndex + 1}`,
            start_time: subStartTime,
            end_time: subEndTime,
            canMove: false,
            canResize: false,
            canChangeGroup: false,
            itemProps: {
              style: {
                background: '#52c41a',
                color: 'white',
                borderRadius: '4px',
                border: '2px solid #52c41a',
                boxShadow: '0 2px 8px rgba(82, 196, 26, 0.3)',
                fontSize: '11px',
                padding: '2px 6px'
              }
            },
            type: 'subslice',
            originalData: subSlice
          });
        });
      }
    });

    console.log('Generated timeline items:', items);
    return items;
  }, [slices]);

  const groups = useMemo(() => {
    if (!slices || slices.length === 0) return [];

    return slices.map((slice, index) => ({
      id: index + 1,
      title: slice.cover_title || slice.title || `切片 ${index + 1}`,
      rightTitle: `${formatTime(slice.duration || 0)} | ${slice.sub_slices?.length || 0} 子切片`,
      stackItems: true
    }));
  }, [slices]);

  const maxTime = Math.max(...timelineItems.map(item => item.end_time));
  const minTime = Math.min(...timelineItems.map(item => item.start_time));
  
  // Set initial visible time range and reset when video changes
  useEffect(() => {
    if (timelineItems.length > 0 && slices && slices.length > 0) {
      const initialVisibleTimeStart = minTime;
      // Calculate total video duration from all slices
      const totalDuration = slices.reduce((total, slice) => total + (slice.duration || 0), 0);
      // Set end time based on actual video content, but limit to reasonable range
      const calculatedEndTime = minTime + (totalDuration * 1000); // Convert to milliseconds
      // Limit to a reasonable maximum (e.g., 6 hours) to prevent overly wide timelines
      const maxReasonableTime = minTime + 21600000; // 6 hours in milliseconds
      const initialVisibleTimeEnd = Math.min(Math.max(maxTime, calculatedEndTime), maxReasonableTime);
      
      if (visibleTimeStart === 0 && visibleTimeEnd === 0) {
        setVisibleTimeStart(initialVisibleTimeStart);
        setVisibleTimeEnd(initialVisibleTimeEnd);
      }
    }
  }, [timelineItems, minTime, maxTime, selectedVideo, slices]);

  const itemRenderer = ({ item, itemContext, getItemProps, getResizeProps }: any) => {
    // Use the style from itemProps or fallback to a default style
    const baseStyle = item.itemProps?.style || {
      background: item.type === 'slice' ? '#1890ff' : '#52c41a',
      color: 'white',
      borderRadius: '6px',
      border: `2px solid ${item.type === 'slice' ? '#1890ff' : '#52c41a'}`,
      boxShadow: `0 2px 8px rgba(${item.type === 'slice' ? '24, 144, 255' : '82, 196, 26'}, 0.3)`,
      fontWeight: 'bold',
      fontSize: '12px',
      padding: '4px 8px'
    };

    const style = {
      ...baseStyle,
      height: item.type === 'slice' ? '40px' : '30px',
      top: item.type === 'slice' ? '0px' : 'auto',
      margin: item.type === 'slice' ? '5px 0' : '2px 0',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    };

    // Calculate duration for display
    const durationSeconds = (item.end_time - item.start_time) / 1000;
    const durationText = ` (${formatTime(durationSeconds)})`;
    
    // Default item props if getItemProps is not available
    const defaultItemProps = {
      style: style,
      onClick: () => {
        setSelectedTimelineItem(item);
        setItemModalVisible(true);
      }
    };

    return (
      <div {...(getItemProps ? getItemProps({ item, style }) : defaultItemProps)}>
        <div style={{ 
          padding: '4px 8px', 
          textAlign: 'center',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          width: '100%'
        }}>
          <Text style={{ color: 'white', fontSize: '12px', fontWeight: 'bold' }}>
            {item.type === 'slice' ? '📹 ' : '📄 '}
            {item.title}
            <Text style={{ color: 'white', fontSize: '11px', fontWeight: 'normal', marginLeft: '4px' }}>
              {durationText}
            </Text>
          </Text>
        </div>
      </div>
    );
  };

  const groupRenderer = ({ group }: any) => {
    // Extract duration from rightTitle if it exists
    let durationText = '';
    if (group.rightTitle) {
      const durationMatch = group.rightTitle.match(/(\d+:\d+:\d+)/);
      if (durationMatch) {
        durationText = ` (${durationMatch[1]})`;
      }
    }
    
    return (
      <div style={{ 
        padding: '12px', 
        backgroundColor: '#f8f9fa',
        borderRight: '2px solid #d9d9d9',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        minWidth: '300px'
      }}>
        <div style={{ 
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          alignItems: 'flex-start'
        }}>
          <Text 
            strong 
            style={{ 
              fontSize: '13px', 
              color: '#1890ff',
              wordBreak: 'break-word',
              lineHeight: '1.4',
              maxWidth: '100%'
            }}
          >
            {group.title}
            {durationText && (
              <Text style={{ 
                color: '#666', 
                fontSize: '12px',
                marginLeft: '8px'
              }}>
                {durationText}
              </Text>
            )}
          </Text>
          {group.rightTitle && (
            <Tag 
              color="blue" 
              style={{ 
                fontSize: '10px', 
                padding: '2px 6px',
                maxWidth: '100%',
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}
            >
              {group.rightTitle}
            </Tag>
          )}
        </div>
      </div>
    );
  };

  if (!selectedVideo) {
    return (
      <Alert
        message="请先选择视频"
        description="选择视频后可以查看切片的时间线可视化"
        type="info"
        showIcon
        style={{ textAlign: 'center', margin: '50px 0' }}
      />
    );
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>加载时间线数据中...</div>
      </div>
    );
  }

  if (timelineItems.length === 0) {
    return (
      <Alert
        message="暂无切片数据"
        description="该视频还没有生成切片，请先进行切片处理"
        type="warning"
        showIcon
        style={{ textAlign: 'center', margin: '50px 0' }}
      />
    );
  }

  return (
    <div style={{ padding: '20px 0' }}>
      <div style={{ marginBottom: '24px', textAlign: 'center' }}>
        <Title level={4} style={{ color: '#1890ff' }}>
          📊 切片时间线可视化
        </Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: '16px' }}>
          时间轴形式展示视频切片，支持交互式浏览和详细信息查看
        </Text>
        <Button 
          type="primary" 
          icon={<FullscreenOutlined />}
          size="large"
          onClick={() => setModalVisible(true)}
          style={{ 
            borderRadius: '20px',
            padding: '8px 24px',
            boxShadow: '0 4px 12px rgba(24, 144, 255, 0.15)'
          }}
        >
          打开完整可视化模式
        </Button>
      </div>
      
      <div style={{ 
        height: `${Math.max(400, groups.length * 60)}px`, 
        minHeight: '400px',
        maxHeight: '800px',
        border: '1px solid #d9d9d9', 
        borderRadius: '8px',
        overflow: 'hidden',
        backgroundColor: '#fafafa',
        position: 'relative'
      }}>
        <Timeline
          groups={groups as any}
          items={timelineItems as any}
          defaultTimeStart={moment(visibleTimeStart)}
          defaultTimeEnd={moment(visibleTimeEnd)}
          visibleTimeStart={visibleTimeStart}
          visibleTimeEnd={visibleTimeEnd}
          onTimeChange={(visibleTimeStart, visibleTimeEnd) => {
            // Allow scrolling by updating the visible time range
            setVisibleTimeStart(visibleTimeStart);
            setVisibleTimeEnd(visibleTimeEnd);
          }}
          itemRenderer={itemRenderer}
          groupRenderer={groupRenderer}
          canMove={false}
          canResize={false}
          canChangeGroup={false}
          stackItems={true}
          lineHeight={60}
          sidebarWidth={320}
          traditionalZoom={true}
          dragSnap={60000} // Snap to 1 minute
          itemTouchSendsClick={false}
        >
          <TimelineHeaders>
            <SidebarHeader>
              {({ getRootProps }) => {
                return <div {...getRootProps()} />;
              }}
            </SidebarHeader>
            <DateHeader 
              unit="primaryHeader"
              labelFormat="MMM DD, YYYY"
              style={{ 
                height: 30, 
                backgroundColor: '#f8f9fa',
                borderBottom: '1px solid #d9d9d9',
                textAlign: 'center',
                fontSize: '14px',
                fontWeight: 'bold'
              }}
            />
            <DateHeader
              labelFormat="mm:ss"
              style={{
                height: 50,
                backgroundColor: '#ffffff',
                borderBottom: '1px solid #d9d9d9',
                textAlign: 'center',
                fontSize: '12px'
              }}
              intervalRenderer={(props: any) => {
                if (!props) return null;
                const { intervalContext, getIntervalProps, data } = props;
                if (!intervalContext || !getIntervalProps) return null;
                return (
                  <div {...getIntervalProps()} style={{
                    height: 50,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderLeft: '1px solid #d9d9d9',
                    backgroundColor: intervalContext.interval % 1200000 < 600000 ? '#fafafa' : '#ffffff'
                  }}>
                    {moment(intervalContext.interval).format('mm:ss')}
                  </div>
                );
              }}
            />
          </TimelineHeaders>
        </Timeline>
      </div>
      
      <div style={{ marginTop: '16px', textAlign: 'center' }}>
        <Space>
          <Tooltip title="蓝色为主切片，绿色为子切片">
            <Tag color="blue">主切片</Tag>
          </Tooltip>
          <Tooltip title="绿色为子切片">
            <Tag color="green">子切片</Tag>
          </Tooltip>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            共 {timelineItems.length} 个时间块 | 使用鼠标滚轮缩放 | 点击项目查看详情
          </Text>
        </Space>
      </div>

      {/* Item Detail Modal */}
      <Modal
        title={selectedTimelineItem?.type === 'slice' ? '主切片详情' : '子切片详情'}
        open={itemModalVisible}
        onCancel={() => setItemModalVisible(false)}
        footer={null}
        width={600}
      >
        {selectedTimelineItem && (
          <Card>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <div>
                <Title level={5} style={{ 
                  margin: 0, 
                  color: selectedTimelineItem.type === 'slice' ? '#1890ff' : '#52c41a' 
                }}>
                  {selectedTimelineItem.type === 'slice' ? '📹 ' : '📄 '}
                  {selectedTimelineItem.title}
                </Title>
              </div>
              
              <div>
                <Text strong>时间范围：</Text>
                <Text code>
                  {formatTime(selectedTimelineItem.start_time / 1000)} - {formatTime(selectedTimelineItem.end_time / 1000)}
                </Text>
                <br />
                <Text type="secondary">
                  持续时间：{formatTime((selectedTimelineItem.end_time - selectedTimelineItem.start_time) / 1000)}
                </Text>
              </div>

              {selectedTimelineItem.originalData.description && (
                <div>
                  <Text strong>描述：</Text>
                  <Paragraph style={{ margin: '8px 0' }}>
                    {selectedTimelineItem.originalData.description}
                  </Paragraph>
                </div>
              )}

              {selectedTimelineItem.originalData.tags && selectedTimelineItem.originalData.tags.length > 0 && (
                <div>
                  <Text strong>标签：</Text>
                  <div style={{ marginTop: '8px' }}>
                    {selectedTimelineItem.originalData.tags.map((tag: string, index: number) => (
                      <Tag key={index} color="blue" style={{ marginRight: '4px' }}>
                        {tag}
                      </Tag>
                    ))}
                  </div>
                </div>
              )}

              {selectedTimelineItem.originalData.file_size && (
                <div>
                  <Text strong>文件大小：</Text>
                  <Text>{formatFileSize(selectedTimelineItem.originalData.file_size)}</Text>
                </div>
              )}
            </Space>
          </Card>
        )}
      </Modal>
      
      {/* Full Screen Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <FullscreenOutlined style={{ color: '#1890ff', fontSize: '24px' }} />
            <Title level={3} style={{ margin: 0, color: '#1890ff' }}>
              📊 切片完整可视化模式
            </Title>
          </div>
        }
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        width="95vw"
        height="90vh"
        style={{ top: '5vh' }}
        footer={null}
        closable={true}
        maskClosable={true}
        destroyOnClose={false}
      >
        <div style={{ 
          maxHeight: 'calc(90vh - 120px)', 
          overflow: 'auto',
          padding: '20px'
        }}>
          {/* Statistics */}
          <div style={{ 
            marginBottom: '30px', 
            padding: '24px', 
            backgroundColor: '#f0f8ff', 
            borderRadius: '12px',
            border: '2px solid #e6f7ff'
          }}>
            <Title level={4} style={{ color: '#1890ff', marginBottom: '16px', textAlign: 'center' }}>
              📈 视频切片统计概览
            </Title>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
              <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#fff', borderRadius: '8px' }}>
                <Text strong style={{ fontSize: '32px', color: '#1890ff' }}>
                  {slices.length}
                </Text>
                <Text type="secondary" style={{ fontSize: '14px' }}>
                  主切片总数
                </Text>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#fff', borderRadius: '8px' }}>
                <Text strong style={{ fontSize: '32px', color: '#52c41a' }}>
                  {slices.reduce((total, slice) => total + (slice.sub_slices?.length || 0), 0)}
                </Text>
                <Text type="secondary" style={{ fontSize: '14px' }}>
                  子切片总数
                </Text>
              </div>
              <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#fff', borderRadius: '8px' }}>
                <Text strong style={{ fontSize: '32px', color: '#722ed1' }}>
                  {formatTime(slices.reduce((total, slice) => total + (slice.duration || 0), 0))}
                </Text>
                <Text type="secondary" style={{ fontSize: '14px' }}>
                  总视频时长
                </Text>
              </div>
            </div>
          </div>

          {/* Full Timeline */}
          <div style={{ 
              height: `${Math.max(400, groups.length * 70)}px`, 
              minHeight: '400px',
              maxHeight: '800px',
              border: '1px solid #d9d9d9', 
              borderRadius: '8px' 
            }}>
            <Timeline
              groups={groups as any}
              items={timelineItems as any}
              defaultTimeStart={moment(visibleTimeStart)}
              defaultTimeEnd={moment(visibleTimeEnd)}
              visibleTimeStart={visibleTimeStart}
              visibleTimeEnd={visibleTimeEnd}
              onTimeChange={(visibleTimeStart, visibleTimeEnd) => {
                // Allow scrolling by updating the visible time range
                setVisibleTimeStart(visibleTimeStart);
                setVisibleTimeEnd(visibleTimeEnd);
              }}
              itemRenderer={itemRenderer}
              groupRenderer={groupRenderer}
              canMove={false}
              canResize={false}
              canChangeGroup={false}
              stackItems={true}
              lineHeight={60}
              sidebarWidth={370}
              traditionalZoom={true}
              dragSnap={60000}
              itemTouchSendsClick={false}
            >
              <TimelineHeaders>
                <SidebarHeader>
                  {({ getRootProps }) => {
                    return <div {...getRootProps()} />;
                  }}
                </SidebarHeader>
                <DateHeader 
                  unit="primaryHeader"
                  labelFormat="MMM DD, YYYY"
                  style={{ 
                    height: 30, 
                    backgroundColor: '#f8f9fa',
                    borderBottom: '1px solid #d9d9d9',
                    textAlign: 'center',
                    fontSize: '14px',
                    fontWeight: 'bold'
                  }}
                />
                <DateHeader
                  labelFormat="mm:ss"
                  style={{
                    height: 50,
                    backgroundColor: '#ffffff',
                    borderBottom: '1px solid #d9d9d9',
                    textAlign: 'center',
                    fontSize: '12px'
                  }}
                  intervalRenderer={(props: any) => {
                    if (!props) return null;
                    const { intervalContext, getIntervalProps, data } = props;
                    if (!intervalContext || !getIntervalProps) return null;
                    return (
                      <div {...getIntervalProps()} style={{
                        height: 50,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderLeft: '1px solid #d9d9d9',
                        backgroundColor: intervalContext.interval % 1200000 < 600000 ? '#fafafa' : '#ffffff'
                      }}>
                        {moment(intervalContext.interval).format('mm:ss')}
                      </div>
                    );
                  }}
                />
              </TimelineHeaders>
            </Timeline>
          </div>

          {/* Legend */}
          <div style={{ marginTop: '20px', textAlign: 'center' }}>
            <Space size="large">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ 
                  width: '20px', 
                  height: '20px', 
                  background: '#1890ff', 
                  borderRadius: '4px',
                  border: '2px solid #1890ff'
                }} />
                <Text>主切片</Text>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ 
                  width: '20px', 
                  height: '20px', 
                  background: '#52c41a', 
                  borderRadius: '4px',
                  border: '2px solid #52c41a'
                }} />
                <Text>子切片</Text>
              </div>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                点击时间块查看详细信息 | 使用滚轮和拖拽进行导航
              </Text>
            </Space>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default SliceTimeline;