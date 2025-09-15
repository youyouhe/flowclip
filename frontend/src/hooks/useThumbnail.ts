import { useState, useEffect } from 'react';
import { videoAPI, resourceAPI } from '../services/api';

// 从YouTube URL提取视频ID的函数
const extractYouTubeVideoId = (url: string): string | null => {
  const regex = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/shorts\/)([^&\n?#]+)/;
  const match = url.match(regex);
  return match ? match[1] : null;
};

// 通用缩略图获取hook
export const useThumbnail = (video: {
  id: number;
  url?: string;
  thumbnail_url?: string;
  thumbnail_path?: string;
}) => {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchThumbnail = async () => {
      if (!video.id) return;
      
      setLoading(true);
      setError(false);
      
      try {
        // 首先尝试使用新的缩略图路径生成URL
        if (video.thumbnail_path) {
          try {
            const response = await videoAPI.getThumbnailUrlByPath(video.thumbnail_path);
            setThumbnailUrl(response.data.download_url);
            setLoading(false);
            return;
          } catch (err) {
            console.error(`通过路径获取视频 ${video.id} 缩略图失败:`, err);
          }
        }
        
        // 如果没有thumbnail_path或获取失败，尝试使用旧的thumbnail_url
        if (video.thumbnail_url) {
          try {
            const response = await videoAPI.getThumbnailDownloadUrl(video.id);
            setThumbnailUrl(response.data.download_url);
            setLoading(false);
            return;
          } catch (err) {
            console.error(`获取视频 ${video.id} 缩略图失败:`, err);
          }
        }
        
        // 如果都没有，生成一个默认的YouTube缩略图URL作为备用
        const youtubeVideoId = extractYouTubeVideoId(video.url || '');
        if (youtubeVideoId) {
          setThumbnailUrl(`https://img.youtube.com/vi/${youtubeVideoId}/default.jpg`);
        } else {
          setThumbnailUrl(null);
        }
      } catch (err) {
        setError(true);
        // 最后的备用方案
        const youtubeVideoId = extractYouTubeVideoId(video.url || '');
        if (youtubeVideoId) {
          setThumbnailUrl(`https://img.youtube.com/vi/${youtubeVideoId}/default.jpg`);
        } else {
          setThumbnailUrl(null);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchThumbnail();
  }, [video.id, video.url, video.thumbnail_url, video.thumbnail_path]);

  return { thumbnailUrl, loading, error };
};