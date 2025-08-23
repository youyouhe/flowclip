export interface User {
  id: number;
  email: string;
  username: string;
  fullName?: string;
  avatarUrl?: string;
  isActive: boolean;
  is_superuser?: boolean;
  createdAt: string;
}

export interface Project {
  id: number;
  name: string;
  description?: string;
  userId: number;
  status: 'created' | 'processing' | 'completed' | 'failed';
  createdAt: string;
  updatedAt?: string;
  videoCount?: number;
  completedVideos?: number;
  totalSlices?: number;
}

export interface Video {
  id: number;
  projectId: number;
  title?: string;
  description?: string;
  url?: string;
  filename?: string;
  filePath?: string;
  duration?: number;
  fileSize?: number;
  thumbnailUrl?: string;
  status: 'pending' | 'downloading' | 'downloaded' | 'processing' | 'completed' | 'failed';
  downloadProgress: number;
  createdAt: string;
  updatedAt?: string;
}

export interface Slice {
  id: number;
  videoId: number;
  title: string;
  description?: string;
  startTime: number;
  endTime: number;
  tags?: string[];
  duration?: number;
  thumbnailUrl?: string;
  videoUrl?: string;
  contentSummary?: string;
  keyPoints?: string[];
  hashtags?: string[];
  status: string;
  uploadedToYoutube: boolean;
  youtubeVideoId?: string;
  youtubeUrl?: string;
  createdAt: string;
  updatedAt?: string;
  subSlices?: SubSlice[];
}

export interface SubSlice {
  id: number;
  sliceId: number;
  title: string;
  description?: string;
  startTime: number;
  endTime: number;
  videoUrl?: string;
  status: string;
  createdAt: string;
  updatedAt?: string;
}

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
}

export interface TaskStatus {
  task_id?: string;
  taskId?: string;
  status: 'pending' | 'started' | 'success' | 'failure' | 'retry' | 'revoked' | 'PROGRESS' | 'SUCCESS' | 'FAILURE';
  result?: any;
  error?: string;
  progress?: number;
  step?: string;
}

export interface AudioInfo {
  videoId: string;
  audioFilename: string;
  minioPath: string;
  objectName: string;
  duration: number;
  fileSize: number;
  audioFormat: string;
}

export interface SplitInfo {
  videoId: string;
  totalSegments: number;
  splitFiles: Array<{
    segmentIndex: number;
    filename: string;
    minioPath: string;
    objectName: string;
    fileSize: number;
  }>;
  segmentationParams: {
    maxSegmentLen: number;
    minSegmentLen: number;
    silenceThresh: number;
    minSilenceLen: number;
  };
}

export interface SrtInfo {
  videoId: string;
  srtFilename: string;
  minioPath: string;
  objectName: string;
  totalSegments: number;
  processingStats: {
    successCount: number;
    failCount: number;
    totalFiles: number;
  };
  asrParams: {
    apiUrl: string;
    lang: string;
    maxWorkers: number;
  };
}

export interface ProcessingStatus {
  status: string;
  progress: number;
  duration?: number;
  totalSegments?: number;
}

export interface StageInfo {
  status: string;
  progress: number;
  color?: string;
}