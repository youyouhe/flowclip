#!/usr/bin/env python3
"""
批量修改路由装饰器添加operation_id
"""

import os
import re

# 定义需要修改的文件和操作ID映射
ROUTE_FIXES = [
    # video_slice.py
    {
        'file': 'app/api/v1/video_slice.py',
        'fixes': [
            {
                'pattern': r'@router\.post\("/validate-slice-data"([^)]*)\)',
                'replacement': r'@router.post("/validate-slice-data"\1, operation_id="validate_slices")'
            },
            {
                'pattern': r'@router\.post\("/process-slices"([^)]*)\)',
                'replacement': r'@router.post("/process-slices"\1, operation_id="process_slices")'
            }
        ]
    },
    # llm.py
    {
        'file': 'app/api/v1/llm.py',
        'fixes': [
            {
                'pattern': r'@router\.post\("/chat"([^)]*)\)',
                'replacement': r'@router.post("/chat"\1, operation_id="llm_chat")'
            }
        ]
    },
    # capcut.py
    {
        'file': 'app/api/v1/capcut.py',
        'fixes': [
            {
                'pattern': r'@router\.get\("/status"([^)]*)\)',
                'replacement': r'@router.get("/status"\1, operation_id="capcut_status")'
            },
            {
                'pattern': r'@router\.post\("/export-slice/{slice_id}"([^)]*)\)',
                'replacement': r'@router.post("/export-slice/{slice_id}"\1, operation_id="export_slice")'
            }
        ]
    },
    # processing.py
    {
        'file': 'app/api/v1/processing.py',
        'fixes': [
            {
                'pattern': r'@router\.get\("/logs/task/{task_id}"([^)]*)\)',
                'replacement': r'@router.get("/logs/task/{task_id}"\1, operation_id="get_task_logs")'
            }
        ]
    },
    # video_processing.py
    {
        'file': 'app/api/v1/video_processing.py',
        'fixes': [
            {
                'pattern': r'@router\.post\("/{video_id}/extract-audio"([^)]*)\)',
                'replacement': r'@router.post("/{video_id}/extract-audio"\1, operation_id="extract_audio")'
            },
            {
                'pattern': r'@router\.post\("/{video_id}/generate-srt"([^)]*)\)',
                'replacement': r'@router.post("/{video_id}/generate-srt"\1, operation_id="generate_srt")'
            }
        ]
    }
]

def fix_operation_ids():
    """批量修复operation_id"""
    for route_fix in ROUTE_FIXES:
        file_path = route_fix['file']
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            continue
            
        print(f"处理文件: {file_path}")
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 应用修复
        modified = False
        for fix in route_fix['fixes']:
            old_content = content
            content = re.sub(fix['pattern'], fix['replacement'], content)
            if content != old_content:
                modified = True
                print(f"  应用修复: {fix['pattern'][:50]}...")
        
        # 写回文件
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ 文件已修改")
        else:
            print(f"  ℹ️  无需修改")

if __name__ == "__main__":
    fix_operation_ids()
    print("批量修复完成!")