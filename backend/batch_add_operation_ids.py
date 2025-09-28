#!/usr/bin/env python3
"""
批量为所有API路由添加operation_id
"""

import os
import re
import glob

def add_operation_id_to_file(file_path, route_configs):
    """为指定文件添加operation_id"""
    print(f"\n处理文件: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    modified_count = 0
    
    for config in route_configs:
        pattern = config['pattern']
        operation_id = config['operation_id']
        
        # 检查是否已经有operation_id
        if f'operation_id="{operation_id}"' in content:
            print(f"  ✓ 已存在: {operation_id}")
            continue
            
        # 查找匹配的路由
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        for match in matches:
            # 检查这个匹配是否已经有operation_id
            matched_text = match.group(0)
            if 'operation_id=' in matched_text:
                print(f"  ✓ 跳过已有operation_id的路由")
                continue
                
            # 在装饰器的最后参数前添加operation_id
            old_decorator = matched_text
            
            # 找到最后的右括号前添加operation_id
            if old_decorator.endswith(')'):
                # 如果装饰器以)结尾，在)前添加operation_id
                if ', ' in old_decorator:
                    new_decorator = old_decorator[:-1] + f', operation_id="{operation_id}")'
                else:
                    # 如果只有路径参数，需要特殊处理
                    new_decorator = old_decorator[:-1] + f', operation_id="{operation_id}")'
            else:
                new_decorator = old_decorator + f', operation_id="{operation_id}"'
            
            content = content.replace(old_decorator, new_decorator)
            modified_count += 1
            print(f"  ✅ 添加: {operation_id}")
    
    # 如果有修改就写回文件
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  📝 文件已更新，共修改 {modified_count} 个路由")
    else:
        print(f"  ℹ️  无需修改")

# 定义所有需要添加operation_id的路由配置
ROUTE_CONFIGURATIONS = {
    'app/api/v1/asr.py': [
        {
            'pattern': r'@router\.get\("/status"[^)]*\)',
            'operation_id': 'asr_status'
        }
    ],
    
    'app/api/v1/capcut.py': [
        {
            'pattern': r'@router\.get\("/status"[^)]*\)',
            'operation_id': 'capcut_status'
        },
        {
            'pattern': r'@router\.post\("/export-slice/\{slice_id\}"[^)]*\)',
            'operation_id': 'export_slice'
        }
    ],
    
    'app/api/v1/llm.py': [
        {
            'pattern': r'@router\.post\("/chat"[^)]*\)',
            'operation_id': 'llm_chat'
        },
        {
            'pattern': r'@router\.get\("/models"[^)]*\)',
            'operation_id': 'get_models'
        },
        {
            'pattern': r'@router\.get\("/system-prompt"[^)]*\)',
            'operation_id': 'get_system_prompt'
        },
        {
            'pattern': r'@router\.post\("/system-prompt"[^)]*\)',
            'operation_id': 'update_system_prompt'
        }
    ],
    
    'app/api/v1/projects.py': [
        {
            'pattern': r'@router\.get\("/\{project_id\}"[^)]*\)',
            'operation_id': 'get_project'
        },
        {
            'pattern': r'@router\.put\("/\{project_id\}"[^)]*\)',
            'operation_id': 'update_project'
        },
        {
            'pattern': r'@router\.delete\("/\{project_id\}"[^)]*\)',
            'operation_id': 'delete_project'
        },
        {
            'pattern': r'@router\.get\("/\{project_id\}/videos"[^)]*\)',
            'operation_id': 'get_project_videos'
        }
    ],
    
    'app/api/v1/processing.py': [
        {
            'pattern': r'@router\.get\("/logs"[^)]*\)',
            'operation_id': 'get_logs'
        },
        {
            'pattern': r'@router\.get\("/logs/task/\{task_id\}"[^)]*\)',
            'operation_id': 'get_task_logs'
        },
        {
            'pattern': r'@router\.get\("/logs/video/\{video_id\}"[^)]*\)',
            'operation_id': 'get_video_logs'
        },
        {
            'pattern': r'@router\.get\("/logs/statistics"[^)]*\)',
            'operation_id': 'get_logs_stats'
        },
        {
            'pattern': r'@router\.delete\("/logs/\{log_id\}"[^)]*\)',
            'operation_id': 'delete_log'
        },
        {
            'pattern': r'@router\.delete\("/logs/task/\{task_id\}"[^)]*\)',
            'operation_id': 'delete_task_logs'
        },
        {
            'pattern': r'@router\.delete\("/logs/video/\{video_id\}"[^)]*\)',
            'operation_id': 'delete_video_logs'
        }
    ],
    
    'app/api/v1/video_processing.py': [
        {
            'pattern': r'@router\.post\("/\{video_id\}/extract-audio"[^)]*\)',
            'operation_id': 'extract_audio'
        },
        {
            'pattern': r'@router\.post\("/\{video_id\}/generate-srt"[^)]*\)',
            'operation_id': 'generate_srt'
        },
        {
            'pattern': r'@router\.get\("/\{video_id\}/task-status/\{task_id\}"[^)]*\)',
            'operation_id': 'get_task_status'
        },
        {
            'pattern': r'@router\.get\("/\{video_id\}/processing-status"[^)]*\)',
            'operation_id': 'get_processing_status'
        }
    ],
    
    'app/api/v1/system_config.py': [
        {
            'pattern': r'@router\.get\("/system-config"[^)]*\)',
            'operation_id': 'get_system_config'
        },
        {
            'pattern': r'@router\.post\("/system-config"[^)]*\)',
            'operation_id': 'update_system_config'
        },
        {
            'pattern': r'@router\.get\("/system-config/service-status/\{service_name\}"[^)]*\)',
            'operation_id': 'service_status'
        },
        {
            'pattern': r'@router\.post\("/test-asr"[^)]*\)',
            'operation_id': 'test_asr'
        }
    ],
    
    'app/api/v1/video_basic.py': [
        {
            'pattern': r'@router\.get\("/"[^)]*\)',
            'operation_id': 'list_videos'
        },
        {
            'pattern': r'@router\.get\("/active"[^)]*\)',
            'operation_id': 'list_active_videos'
        },
        {
            'pattern': r'@router\.get\("/\{video_id\}"[^)]*\)',
            'operation_id': 'get_video'
        },
        {
            'pattern': r'@router\.put\("/\{video_id\}"[^)]*\)',
            'operation_id': 'update_video'
        },
        {
            'pattern': r'@router\.delete\("/\{video_id\}"[^)]*\)',
            'operation_id': 'delete_video'
        }
    ],
    
    'app/api/v1/video_download.py': [
        {
            'pattern': r'@router\.post\("/download"[^)]*\)',
            'operation_id': 'download_video'
        },
        {
            'pattern': r'@router\.get\("/\{video_id\}/download-url"[^)]*\)',
            'operation_id': 'get_video_download_url'
        }
    ],
    
    'app/api/v1/status.py': [
        {
            'pattern': r'@router\.get\("/videos/\{video_id\}"[^)]*\)',
            'operation_id': 'get_video_status'
        },
        {
            'pattern': r'@router\.get\("/tasks/\{task_id\}"[^)]*\)',
            'operation_id': 'get_task_status_detail'
        },
        {
            'pattern': r'@router\.get\("/dashboard"[^)]*\)',
            'operation_id': 'get_dashboard'
        },
        {
            'pattern': r'@router\.get\("/videos/running"[^)]*\)',
            'operation_id': 'get_running_videos'
        }
    ]
}

def main():
    """主函数"""
    print("🚀 开始批量添加operation_id...")
    
    total_files = 0
    total_routes = 0
    
    for file_path, route_configs in ROUTE_CONFIGURATIONS.items():
        if os.path.exists(file_path):
            add_operation_id_to_file(file_path, route_configs)
            total_files += 1
            total_routes += len(route_configs)
        else:
            print(f"⚠️  文件不存在: {file_path}")
    
    print(f"\n✅ 批量处理完成!")
    print(f"📊 处理了 {total_files} 个文件，{total_routes} 个路由配置")
    print("\n🎯 现在所有重要的API都有简短的operation_id了!")

if __name__ == "__main__":
    main()