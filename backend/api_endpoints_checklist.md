# Flowclip API 端点清单 (共 95 个)

请在每行前添加 ✅ 表示包含在MCP中，或 ❌ 表示排除

格式：[状态] [方法] [路径] # [文件] - [相对路径]

## asr.py (1 个端点)
[✅] GET    /api/v1/asr/status                                           # asr.py - /status

## auth.py (3 个端点)
[ ] GET    /api/v1/auth/me                                              # auth.py - /me
[✅] POST   /api/v1/auth/login                                           # auth.py - /login
[ ] POST   /api/v1/auth/register                                        # auth.py - /register

## capcut.py (3 个端点)
[ ] GET    /api/v1/capcut/proxy-resource/{resource_path:path}           # capcut.py - /proxy-resource/{resource_path:path}
[✅] GET    /api/v1/capcut/status                                        # capcut.py - /status
[✅] POST   /api/v1/capcut/export-slice/{slice_id}                       # capcut.py - /export-slice/{slice_id}

## llm.py (4 个端点)
[ ] GET    /api/v1/llm/models                                           # llm.py - /models
[ ] GET    /api/v1/llm/system-prompt                                    # llm.py - /system-prompt
[✅] POST   /api/v1/llm/chat                                             # llm.py - /chat
[ ] POST   /api/v1/llm/system-prompt                                    # llm.py - /system-prompt

## minio_resources.py (1 个端点)
[ ] GET    /api/v1/minio/minio-url                                      # minio_resources.py - /minio-url

## processing.py (7 个端点)
[ ] DELETE /api/v1/processing/logs/task/{task_id}                       # processing.py - /logs/task/{task_id}
[ ] DELETE /api/v1/processing/logs/video/{video_id}                     # processing.py - /logs/video/{video_id}
[ ] DELETE /api/v1/processing/logs/{log_id}                             # processing.py - /logs/{log_id}
[ ] GET    /api/v1/processing/logs                                      # processing.py - /logs
[ ] GET    /api/v1/processing/logs/statistics                           # processing.py - /logs/statistics
[✅] GET    /api/v1/processing/logs/task/{task_id}                       # processing.py - /logs/task/{task_id}
[ ] GET    /api/v1/processing/logs/video/{video_id}                     # processing.py - /logs/video/{video_id}

## projects.py (6 个端点)
[ ] DELETE /api/v1/projects/{project_id}                                # projects.py - /{project_id}
[✅] GET    /api/v1/projects/                                            # projects.py - /
[ ] GET    /api/v1/projects/{project_id}                                # projects.py - /{project_id}
[✅] GET    /api/v1/projects/{project_id}/videos                         # projects.py - /{project_id}/videos
[✅] POST   /api/v1/projects/                                            # projects.py - /
[ ] PUT    /api/v1/projects/{project_id}                                # projects.py - /{project_id}

## resource.py (13 个端点)
[ ] DELETE /api/v1/resources/tags/{tag_id}                              # resource.py - /tags/{tag_id}
[ ] DELETE /api/v1/resources/{resource_id}                              # resource.py - /{resource_id}
[ ] GET    /api/v1/resources/                                           # resource.py - /
[ ] GET    /api/v1/resources/tags                                       # resource.py - /tags
[ ] GET    /api/v1/resources/thumbnail-url                              # resource.py - /thumbnail-url
[ ] GET    /api/v1/resources/{resource_id}                              # resource.py - /{resource_id}
[ ] GET    /api/v1/resources/{resource_id}/download-url                 # resource.py - /{resource_id}/download-url
[ ] GET    /api/v1/resources/{resource_id}/view-url                     # resource.py - /{resource_id}/view-url
[ ] POST   /api/v1/resources/                                           # resource.py - /
[ ] POST   /api/v1/resources/tags                                       # resource.py - /tags
[ ] POST   /api/v1/resources/upload                                     # resource.py - /upload
[ ] PUT    /api/v1/resources/{resource_id}                              # resource.py - /{resource_id}
[ ] PUT    /api/v1/resources/{resource_id}/activate                     # resource.py - /{resource_id}/activate

## resource_tag.py (6 个端点)
[ ] DELETE /api/v1/resource-tags/{tag_id}                               # resource_tag.py - /{tag_id}
[ ] GET    /api/v1/resource-tags/                                       # resource_tag.py - /
[ ] GET    /api/v1/resource-tags/{tag_id}                               # resource_tag.py - /{tag_id}
[ ] POST   /api/v1/resource-tags/                                       # resource_tag.py - /
[ ] POST   /api/v1/resource-tags/batch-create                           # resource_tag.py - /batch-create
[ ] PUT    /api/v1/resource-tags/{tag_id}                               # resource_tag.py - /{tag_id}

## status.py (9 个端点)
[ ] GET    /api/v1/status/celery/{celery_task_id}                       # status.py - /celery/{celery_task_id}
[ ] GET    /api/v1/status/dashboard                                     # status.py - /dashboard
[ ] GET    /api/v1/status/tasks/{task_id}                               # status.py - /tasks/{task_id}
[ ] GET    /api/v1/status/tasks/{task_id}/logs                          # status.py - /tasks/{task_id}/logs
[ ] GET    /api/v1/status/videos/running                                # status.py - /videos/running
[ ] GET    /api/v1/status/videos/{video_id}                             # status.py - /videos/{video_id}
[ ] GET    /api/v1/status/videos/{video_id}/status/summary              # status.py - /videos/{video_id}/status/summary
[ ] GET    /api/v1/status/videos/{video_id}/tasks                       # status.py - /videos/{video_id}/tasks
[ ] POST   /api/v1/status/videos/{video_id}/reset                       # status.py - /videos/{video_id}/reset

## system_config.py (6 个端点)
[ ] GET    /api/v1/system/system-config                                 # system_config.py - /system-config
[✅] GET    /api/v1/system/system-config/service-status/{service_name}   # system_config.py - /system-config/service-status/{service_name}
[ ] POST   /api/v1/system/system-config                                 # system_config.py - /system-config
[ ] POST   /api/v1/system/system-config/batch                           # system_config.py - /system-config/batch
[ ] POST   /api/v1/system/system-config/reload-configs                  # system_config.py - /system-config/reload-configs
[ ] POST   /api/v1/system/test-asr                                      # system_config.py - /test-asr

## upload.py (4 个端点)
[ ] GET    /api/v1/upload/status/{upload_id}                            # upload.py - /status/{upload_id}
[ ] GET    /api/v1/upload/youtube/auth-url                              # upload.py - /youtube/auth-url
[ ] POST   /api/v1/upload/youtube/callback                              # upload.py - /youtube/callback
[ ] POST   /api/v1/upload/youtube/{slice_id}                            # upload.py - /youtube/{slice_id}

## video_basic.py (5 个端点)
[ ] DELETE /api/v1/videos/{video_id}                                    # video_basic.py - /{video_id}
[ ] GET    /api/v1/videos/                                              # video_basic.py - /
[ ] GET    /api/v1/videos/active                                        # video_basic.py - /active
[ ] GET    /api/v1/videos/{video_id}                                    # video_basic.py - /{video_id}
[ ] PUT    /api/v1/videos/{video_id}                                    # video_basic.py - /{video_id}

## video_download.py (2 个端点)
[ ] GET    /api/v1/videos/{video_id}/download-url                       # video_download.py - /{video_id}/download-url
[ ] POST   /api/v1/videos/download                                      # video_download.py - /download

## video_file_download.py (6 个端点)
[ ] GET    /api/v1/videos/{video_id}/audio-download-url                 # video_file_download.py - /{video_id}/audio-download-url
[ ] GET    /api/v1/videos/{video_id}/srt-content                        # video_file_download.py - /{video_id}/srt-content
[ ] GET    /api/v1/videos/{video_id}/srt-download                       # video_file_download.py - /{video_id}/srt-download
[ ] GET    /api/v1/videos/{video_id}/srt-download-url                   # video_file_download.py - /{video_id}/srt-download-url
[ ] GET    /api/v1/videos/{video_id}/thumbnail-download-url             # video_file_download.py - /{video_id}/thumbnail-download-url
[ ] GET    /api/v1/videos/{video_id}/video-download                     # video_file_download.py - /{video_id}/video-download

## video_processing.py (4 个端点)
[ ] GET    /api/v1/processing/{video_id}/processing-status              # video_processing.py - /{video_id}/processing-status
[ ] GET    /api/v1/processing/{video_id}/task-status/{task_id}          # video_processing.py - /{video_id}/task-status/{task_id}
[✅] POST   /api/v1/processing/{video_id}/extract-audio                  # video_processing.py - /{video_id}/extract-audio
[✅] POST   /api/v1/processing/{video_id}/generate-srt                   # video_processing.py - /{video_id}/generate-srt

## video_slice.py (13 个端点)
[ ] DELETE /api/v1/video-slice/analysis/{analysis_id}                   # video_slice.py - /analysis/{analysis_id}
[ ] DELETE /api/v1/video-slice/slice/{slice_id}                         # video_slice.py - /slice/{slice_id}
[ ] DELETE /api/v1/video-slice/sub-slice/{sub_slice_id}                 # video_slice.py - /sub-slice/{sub_slice_id}
[ ] GET    /api/v1/video-slice/slice-detail/{slice_id}                  # video_slice.py - /slice-detail/{slice_id}
[ ] GET    /api/v1/video-slice/slice-download-url/{slice_id}            # video_slice.py - /slice-download-url/{slice_id}
[ ] GET    /api/v1/video-slice/slice-srt-content/{slice_id}             # video_slice.py - /slice-srt-content/{slice_id}
[ ] GET    /api/v1/video-slice/slice-sub-slices/{slice_id}              # video_slice.py - /slice-sub-slices/{slice_id}
[ ] GET    /api/v1/video-slice/sub-slice-download-url/{sub_slice_id}    # video_slice.py - /sub-slice-download-url/{sub_slice_id}
[ ] GET    /api/v1/video-slice/sub-slice-srt-content/{sub_slice_id}     # video_slice.py - /sub-slice-srt-content/{sub_slice_id}
[ ] GET    /api/v1/video-slice/video-analyses/{video_id}                # video_slice.py - /video-analyses/{video_id}
[ ] GET    /api/v1/video-slice/video-slices/{video_id}                  # video_slice.py - /video-slices/{video_id}
[✅] POST   /api/v1/video-slice/process-slices                           # video_slice.py - /process-slices
[✅] POST   /api/v1/video-slice/validate-slice-data                      # video_slice.py - /validate-slice-data

## video_upload.py (2 个端点)
[ ] POST   /api/v1/videos/upload                                        # video_upload.py - /upload
[ ] POST   /api/v1/videos/upload-chunk                                  # video_upload.py - /upload-chunk

## websocket.py (2 个端点)
[ ] WEBSOCKET /api/v1/ws/progress/{token}                               # websocket.py - /progress/{token}
[ ] WEBSOCKET /api/v1/ws/test                                           # websocket.py - /test

---

**总计: 95 个API端点**

**使用说明:**
1. 将 `[ ]` 替换为 `[✅]` 表示包含在MCP中
2. 将 `[ ]` 替换为 `[❌]` 表示排除
3. 完成筛选后，请告知我更新 mcp_server.py

**建议筛选原则:**
- ✅ 核心业务功能（认证、项目、视频、处理）
- ✅ 状态查询和监控
- ❌ 系统配置和管理功能
- ❌ 复杂的文件上传/下载
- ❌ WebSocket实时通信
- ❌ 内部工具和代理功能
