#!/usr/bin/env python3
"""
TUS ASR Client
A complete TUS client for audio file upload and ASR processing using the tusdk-resumable
"""

import os
import asyncio
import aiohttp
from aiohttp import web, FormData
import json
import time
import signal
import threading
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import requests

logger = logging.getLogger(__name__)


class TusClient:
    """TUS client for uploading audio files and receiving ASR results

    Args:
        api_url: URL of the Tus API server
        tus_url: URL of the Tus upload server
        callback_listener_port: Port for the callback listener server
        callback_host: Host IP for callback URLs ("auto" for auto-detection, "localhost" for local testing)
        max_retries: Maximum number of retries for failed operations
    """

    def __init__(self,
                 api_url: str = "http://localhost:8000",
                 tus_url: str = "http://localhost:1080",
                 callback_listener_port: int = 9090,
                 callback_host: str = "auto",
                 max_retries: int = 3):
        self.api_url = api_url.rstrip('/')
        self.tus_url = tus_url.rstrip('/')
        self.callback_port = callback_listener_port
        self.callback_host = callback_host
        self.max_retries = max_retries
        self.completed_tasks = {}
        self.running = True

        # Signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def run_async(self, audio_file_path: str, metadata: Dict[str, Any] = None):
        """Main client execution (async version)"""
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        if not audio_path.is_file():
            raise ValueError(f"Path is not a file: {audio_file_path}")

        logger.info("Starting TUS ASR Client")
        logger.info(f"API URL: {self.api_url}")
        logger.info(f"TUS URL: {self.tus_url}")
        logger.info(f"Audio file: {audio_file_path}")
        logger.info(f"File size: {audio_path.stat().st_size} bytes")

        # Start callback listener in background
        callback_thread = threading.Thread(target=self._start_callback_server)
        callback_thread.daemon = True
        callback_thread.start()
        time.sleep(0.5)  # Give callback server time to start

        try:
            # Execute upload and wait for results
            srt_content = await self._process_audio_file(audio_file_path, metadata or {})
            return srt_content

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Client execution failed: {e}")
            raise
        finally:
            self.running = False

    def run(self, audio_file_path: str, metadata: Dict[str, Any] = None):
        """Main client execution (sync wrapper)"""
        try:
            # Try to run in existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError("Cannot use asyncio.run() in running event loop")
            else:
                # Use existing loop
                return loop.run_until_complete(self.run_async(audio_file_path, metadata))
        except RuntimeError:
            # Create new event loop
            return asyncio.run(self.run_async(audio_file_path, metadata))

    async def _process_audio_file(self, audio_file_path: str, metadata: Dict[str, Any]) -> str:
        """Process an audio file through the system"""
        audio_path = Path(audio_file_path)

        # Step 1: Create ASR task
        logger.info("📝 Step 1: Creating ASR task...")
        task = await self._create_task(audio_file_path, metadata)
        task_id = task['task_id']
        upload_url = task['upload_url']

        logger.info(f"✅ Task created: {task_id}")
        logger.info(f"📤 Upload URL: {upload_url}")

        # Step 2: Upload file using TUS
        logger.info("📤 Step 2: Uploading file via TUS...")
        await self._upload_file_via_tus(audio_file_path, upload_url)

        logger.info("✅ File upload completed")

        # Step 3: Wait for ASR processing completion
        logger.info("🎧 Step 3: Waiting for ASR processing...")

        # Poll for task status or wait for callback
        srt_content = await self._wait_for_results(task_id)

        logger.info("✅ ASR processing completed")
        return srt_content

    async def _create_task(self, audio_file_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create ASR task and get upload URL"""
        audio_path = Path(audio_file_path)

        # Prepare request payload
        payload = {
            "filename": audio_path.name,
            "filesize": audio_path.stat().st_size,
            "metadata": {
                "language": metadata.get("language", "auto"),
                "model": metadata.get("model", "large-v3-turbo")
            }
        }

        # Generate callback URL for this task
        if self.callback_host == "auto":
            # Auto-detect the local IP address
            import socket
            try:
                # Create a temporary socket to connect to external server to determine local IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))  # Connect to Google DNS (doesn't send data)
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                # Fallback to localhost if auto-detection fails
                local_ip = "localhost"
            callback_url = f"http://{local_ip}:{self.callback_port}/callback"
        else:
            callback_url = f"http://{self.callback_host}:{self.callback_port}/callback"

        if callback_url:
            payload["callback_url"] = callback_url

        logger.info(f"Creating task with payload: {json.dumps(payload, indent=2)}")

        # Use synchronous requests for API calls (easier to handle)
        # In a production setup, you might want to use aiohttp
        response = requests.post(
            f"{self.api_url}/api/v1/asr-tasks",
            json=payload,
            timeout=30
        )

        response.raise_for_status()
        result = response.json()

        if 'task_id' not in result or 'upload_url' not in result:
            raise ValueError(f"Invalid API response: {result}")

        # Store task_id for use throughout the process
        self.current_task_id = result['task_id']

        return result

    async def _upload_file_via_tus(self, audio_file_path: str, upload_url: str) -> None:
        """Upload file using TUS protocol"""
        audio_path = Path(audio_file_path)
        file_size = audio_path.stat().st_size

        logger.info(f"Uploading {audio_path.name} ({file_size} bytes)")

        # Step 1: Create upload (POST to Tus endpoint)
        upload_id = await self._create_tus_upload(upload_url.split('/')[-1], file_size, audio_path.name)

        # Step 2: Upload data in chunks
        await self._upload_tus_data(upload_id, audio_path)

        logger.info(f"TUS upload completed for {audio_path.name}")

    async def _create_tus_upload(self, upload_id: str, file_size: int, filename: str) -> str:
        """Create TUS upload"""
        # Include task_id in upload metadata so TUS server can associate upload with task
        task_id = getattr(self, 'current_task_id', None)

        metadata_parts = [f'filename {filename}']
        if task_id:
            metadata_parts.append(f'task_id {task_id}')

        headers = {
            'Tus-Resumable': '1.0.0',
            'Upload-Length': str(file_size),
            'Upload-Metadata': ', '.join(metadata_parts)
        }

        async with aiohttp.ClientSession() as session:
            url = f"{self.tus_url}/files"
            logger.info(f"Creating TUS upload at {url}")

            async with session.post(url, headers=headers) as response:
                response.raise_for_status()

                # Extract upload URL from Location header
                upload_url = response.headers.get('Location', '')
                if not upload_url:
                    raise ValueError("No Location header in TUS response")

                # Extract upload ID from URL
                actual_upload_id = upload_url.split('/')[-1]
                logger.info(f"TUS upload created with ID: {actual_upload_id}")

                return actual_upload_id

    async def _upload_tus_data(self, upload_id: str, file_path: Path) -> None:
        """Upload file data to TUS server"""
        chunk_size = 1024 * 1024  # 1MB chunks
        offset = 0

        with open(file_path, 'rb') as f:
            comperator = lambda f: f.seek(0, 2) or f.tell()

            async with aiohttp.ClientSession() as session:
                while offset < file_path.stat().st_size:
                    # Seek to offset (for resume support)
                    f.seek(offset)

                    # Read chunk
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    # Upload chunk
                    headers = {
                        'Tus-Resumable': '1.0.0',
                        'Upload-Offset': str(offset),
                        'Content-Type': 'application/offset+octet-stream'
                    }

                    url = f"{self.tus_url}/files/{upload_id}"
                    logger.info(f"Uploading chunk: offset={offset}, size={len(chunk)}")

                    async with session.patch(url, data=chunk, headers=headers) as response:
                        response.raise_for_status()

                        # Update offset
                        new_offset = int(response.headers['Upload-Offset'])
                        if new_offset != offset + len(chunk):
                            raise ValueError(f"Offset mismatch: expected {offset + len(chunk)}, got {new_offset}")

                        offset = new_offset

        logger.info(f"Upload completed: final offset {offset}")

    async def _wait_for_results(self, task_id: str) -> str:
        """Wait for ASR processing results"""
        callback_received = asyncio.Event()
        srt_content = None
        error_message = None

        # Set up callback timeout
        timeout_seconds = 1800  # 30 minutes
        start_time = time.time()

        logger.info(f"Waiting for results on task {task_id} (timeout: {timeout_seconds}s)")
        logger.info(f"Current completed_tasks keys before adding: {list(self.completed_tasks.keys())}")

        # Create a future for callback
        callback_future = asyncio.Future()

        # Set up callback handler
        async def callback_handler(request):
            try:
                logger.info(f"Callback handler triggered for task {task_id}")
                payload = await request.json()
                logger.info(f"Received callback payload: {json.dumps(payload, indent=2)}")

                received_task_id = payload.get('task_id')
                logger.info(f"Received task_id: {received_task_id}, expected task_id: {task_id}")

                if received_task_id == task_id:
                    logger.info(f"✅ Received callback for task {task_id}")
                    status = payload.get('status')
                    logger.info(f"Status: {status}")

                    if status == 'completed':
                        logger.info(f"Task {task_id} completed, processing...")
                        # Get SRT content from download URL
                        srt_url = payload.get('srt_url', f"{self.api_url}/api/v1/tasks/{task_id}/download")
                        logger.info(f"srt_url: {srt_url}")
                        srt_content = await self._download_srt(srt_url)
                        logger.info(f"Downloaded SRT content length: {len(srt_content) if srt_content else 0}")
                        callback_future.set_result(srt_content)
                        logger.info(f"Set result for task {task_id}")
                    else:
                        error_msg = payload.get('error_message', 'Unknown error')
                        logger.error(f"Task failed: {error_msg}")
                        callback_future.set_exception(RuntimeError(error_msg))
                        logger.info(f"Set exception for task {task_id}")
                else:
                    logger.warning(f"Received callback for different task: {received_task_id}")

                return web.Response(text='OK')

            except Exception as e:
                logger.error(f"Error handling callback: {e}")
                logger.exception(e)  # Log full traceback
                return web.Response(status=500, text=str(e))

        # Store callback reference for polling fallback
        logger.info(f"Storing callback future for task {task_id}")
        self.completed_tasks[task_id] = callback_future
        logger.info(f"Current completed_tasks keys after adding: {list(self.completed_tasks.keys())}")

        try:
            # Custom wait mechanism that can be interrupted
            check_interval = 1.0  # Check every second
            waited_time = 0

            while waited_time < timeout_seconds:
                # Check if interrupted
                if not self.running:
                    raise KeyboardInterrupt("User requested shutdown")

                # Check if callback is done
                if callback_future.done():
                    result = callback_future.result()
                    # If result is a dict with completion info, download SRT content
                    if isinstance(result, dict) and result.get('status') == 'completed':
                        task_id = result.get('task_id')
                        srt_url = result.get('srt_url', f"{self.api_url}/api/v1/tasks/{task_id}/download")
                        # If srt_url is relative (doesn't start with http), make it a full URL
                        if srt_url and not srt_url.startswith('http'):
                            srt_url = f"{self.api_url}{srt_url}"
                        srt_content = await self._download_srt(srt_url)
                        return srt_content
                    else:
                        return result

                await asyncio.sleep(check_interval)
                waited_time += check_interval

            # Timeout reached
            raise asyncio.TimeoutError("Callback not received")

        except asyncio.TimeoutError:
            logger.warning(f"Callback timeout, falling back to polling for task {task_id}")

            # Fallback to polling
            while time.time() - start_time < timeout_seconds and self.running:
                try:
                    status = await self._poll_task_status(task_id)

                    if status['status'] == 'completed':
                        srt_url = f"{self.api_url}/api/v1/tasks/{task_id}/download"
                        srt_content = await self._download_srt(srt_url)
                        return srt_content
                    elif status['status'] == 'failed':
                        error_msg = status.get('error_message', 'Task failed')
                        raise RuntimeError(f"Task failed: {error_msg}")

                    logger.info(f"Task status: {status['status']}, waiting...")
                    await asyncio.sleep(5)

                except Exception as e:
                    logger.error(f"Error polling task status: {e}")
                    await asyncio.sleep(5)

            raise TimeoutError(f"Timeout waiting for task {task_id} completion")

    async def _poll_task_status(self, task_id: str) -> Dict[str, Any]:
        """Poll task status via API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/api/v1/asr-tasks/{task_id}/status"

                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Status API returned {response.status}")
                        return {"status": "unknown"}

        except Exception as e:
            logger.error(f"Error getting task status: {e}")
            return {"status": "unknown"}

    async def _download_srt(self, srt_url: str) -> str:
        """Download SRT content from given URL (handles both JSON and text responses)"""
        try:
            logger.info(f"Downloading SRT from: {srt_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(srt_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    response.raise_for_status()

                    # Try to parse as JSON first (matches load_balancer format)
                    try:
                        result = await response.json()
                        if result.get("code") == 0 and result.get("data"):
                            srt_content = result["data"]
                            logger.info(f"Downloaded SRT content from JSON response ({len(srt_content)} chars)")
                            return srt_content
                        else:
                            raise ValueError(f"Invalid JSON response format: {result}")
                    except aiohttp.ContentTypeError:
                        # If not JSON, try as plain text
                        srt_content = await response.text()
                        logger.info(f"Downloaded SRT content as plain text ({len(srt_content)} chars)")
                        return srt_content

        except Exception as e:
            logger.error(f"Error downloading SRT: {e}")
            raise

    def _start_callback_server(self):
        """Start callback HTTP server in background thread"""
        async def callback_handler(request):
            try:
                logger.info("Callback handler triggered")
                logger.info(f"Request method: {request.method}")
                logger.info(f"Request headers: {dict(request.headers)}")
                logger.info(f"Request remote: {request.remote}")

                # Check content type
                content_type = request.headers.get('Content-Type', '')
                logger.info(f"Content-Type: {content_type}")

                payload = await request.json()
                logger.info(f"Received callback: {json.dumps(payload, indent=2)}")

                task_id = payload.get('task_id')
                logger.info(f"Processing callback for task_id: {task_id}")
                logger.info(f"Current completed_tasks keys: {list(self.completed_tasks.keys())}")

                if task_id in self.completed_tasks:
                    logger.info(f"Found task {task_id} in completed_tasks")
                    future = self.completed_tasks[task_id]

                    if not future.done():
                        logger.info(f"Future for task {task_id} is not done, processing...")
                        if payload.get('status') == 'completed':
                            logger.info(f"Task {task_id} completed, setting result")
                            # For completed tasks, we'll download SRT content later
                            # Mark completion and let polling fallback handle download
                            # Ensure srt_url is a full URL if it's relative
                            srt_url = payload.get('srt_url')
                            logger.info(f"Original srt_url: {srt_url}")
                            if srt_url and not srt_url.startswith('http'):
                                srt_url = f"{self.api_url}{srt_url}"
                                logger.info(f"Modified srt_url: {srt_url}")
                            future.set_result({'status': 'completed', 'task_id': task_id, 'srt_url': srt_url})
                            logger.info(f"Set result for task {task_id}")
                        else:
                            error_msg = payload.get('error_message', 'Task failed')
                            logger.info(f"Task {task_id} failed with error: {error_msg}")
                            future.set_exception(RuntimeError(error_msg))
                            logger.info(f"Set exception for task {task_id}")

                    # Clean up
                    logger.info(f"Cleaning up task {task_id} from completed_tasks")
                    del self.completed_tasks[task_id]
                    logger.info(f"Task {task_id} removed from completed_tasks")

                else:
                    logger.warning(f"Task {task_id} not found in completed_tasks")
                    logger.info(f"Available task IDs: {list(self.completed_tasks.keys())}")

                logger.info("Returning OK response")
                return web.Response(text='OK')

            except Exception as e:
                logger.error(f"Callback error: {e}")
                logger.exception(e)  # Log full traceback
                return web.Response(status=500, text=str(e))

        async def create_app():
            app = web.Application()
            app.router.add_post('/callback', callback_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', self.callback_port)
            await site.start()

            logger.info(f"Callback server started on port {self.callback_port}")
            if self.callback_host == "auto":
                logger.info(f"Callback URL (auto-detected): http://[YOUR_LOCAL_IP]:{self.callback_port}/callback")
            else:
                logger.info(f"Callback URL: http://{self.callback_host}:{self.callback_port}/callback")

            # Keep running
            while self.running:
                await asyncio.sleep(1)

        try:
            asyncio.run(create_app())
        except Exception as e:
            logger.error(f"Callback server failed: {e}")


def main():
    """Main entry point"""
    import sys
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description='TUS ASR Client')
    parser.add_argument('file', help='Audio file to process')
    parser.add_argument('--api-url', default='http://localhost:8000', help='API server URL')
    parser.add_argument('--tus-url', default='http://localhost:1080', help='TUS server URL')
    parser.add_argument('--callback-port', type=int, default=9090, help='Callback listener port')
    parser.add_argument('--callback-host', default='auto', help='Callback host IP (use "auto" for auto-detection, "localhost" for local testing)')
    parser.add_argument('--language', default='auto', help='Audio language')
    parser.add_argument('--model', default='large-v3-turbo', help='Whisper model')
    parser.add_argument('--output', help='Output file for SRT content')

    args = parser.parse_args()

    # Create and run client
    client = TusClient(
        api_url=args.api_url,
        tus_url=args.tus_url,
        callback_listener_port=args.callback_port,
        callback_host=args.callback_host
    )

    metadata = {
        'language': args.language,
        'model': args.model
    }

    try:
        # Run client - this will handle event loop properly
        srt_content = client.run(args.file, metadata)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            logger.info(f"SRT content saved to {args.output}")
        else:
            print("\n" + "="*50)
            print("SRT TRANSCRIPTION RESULT:")
            print("="*50)
            print(srt_content)
            print("="*50)

    except Exception as e:
        logger.error(f"Client failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()