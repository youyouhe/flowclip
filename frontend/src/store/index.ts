import { create } from 'zustand'
import { User, Project, Video, Slice } from '../types'

interface AppState {
  user: User | null
  setUser: (user: User | null) => void
  
  projects: Project[]
  setProjects: (projects: Project[]) => void
  addProject: (project: Project) => void
  updateProject: (id: number, project: Partial<Project>) => void
  deleteProject: (id: number) => void
  
  videos: Video[]
  setVideos: (videos: Video[]) => void
  addVideo: (video: Video) => void
  updateVideo: (id: number, video: Partial<Video>) => void
  
  slices: Slice[]
  setSlices: (slices: Slice[]) => void
  addSlice: (slice: Slice) => void
  updateSlice: (id: number, slice: Partial<Slice>) => void
}

export const useStore = create<AppState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  
  projects: [],
  setProjects: (projects) => set({ projects }),
  addProject: (project) => set((state) => ({ projects: [...state.projects, project] })),
  updateProject: (id, project) => set((state) => ({
    projects: state.projects.map(p => p.id === id ? { ...p, ...project } : p)
  })),
  deleteProject: (id) => set((state) => ({
    projects: state.projects.filter(p => p.id !== id)
  })),
  
  videos: [],
  setVideos: (videos) => set({ videos }),
  addVideo: (video) => set((state) => ({ videos: [...state.videos, video] })),
  updateVideo: (id, video) => set((state) => ({
    videos: state.videos.map(v => v.id === id ? { ...v, ...video } : v)
  })),
  
  slices: [],
  setSlices: (slices) => set({ slices }),
  addSlice: (slice) => set((state) => ({ slices: [...state.slices, slice] })),
  updateSlice: (id, slice) => set((state) => ({
    slices: state.slices.map(s => s.id === id ? { ...s, ...slice } : s)
  })),
}))