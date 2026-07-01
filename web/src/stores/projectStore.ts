import { create } from "zustand";
import type { AnalysisModuleKey, CaseResults, Project } from "../types";
import * as api from "../api";

type ProjectState = {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  error: string | null;
  fetchProjects: () => Promise<void>;
  fetchProject: (id: string) => Promise<Project | null>;
  createProject: (data: Partial<Project>) => Promise<Project>;
  updateProject: (id: string, data: Partial<Project>) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  uploadFile: (
    projectId: string,
    file: File,
    fileType?: string,
    isPrimary?: boolean,
    documentLabel?: string,
    fileSections?: AnalysisModuleKey[]
  ) => Promise<void>;
  removeFile: (projectId: string, fileId: string) => Promise<void>;
  saveRules: (projectId: string, rules: Project["customRules"]) => Promise<void>;
};

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null });
    try {
      const projects = await api.listProjects();
      set({ projects, loading: false });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load projects", loading: false });
    }
  },

  fetchProject: async (id) => {
    set({ loading: true, error: null });
    try {
      const project = await api.getProject(id);
      set({ currentProject: project, loading: false });
      return project;
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load project", loading: false });
      return null;
    }
  },

  createProject: async (data) => {
    const project = await api.createProject(data);
    set({ projects: [project, ...get().projects] });
    return project;
  },

  updateProject: async (id, data) => {
    const updated = await api.updateProject(id, data);
    set({
      projects: get().projects.map((p) => (p.id === id ? updated : p)),
      currentProject: get().currentProject?.id === id ? updated : get().currentProject,
    });
  },

  deleteProject: async (id) => {
    await api.deleteProject(id);
    set({
      projects: get().projects.filter((p) => p.id !== id),
      currentProject: get().currentProject?.id === id ? null : get().currentProject,
    });
  },

  uploadFile: async (projectId, file, fileType, isPrimary, documentLabel, fileSections) => {
    await api.uploadProjectFile(projectId, file, fileType, isPrimary, documentLabel, fileSections);
    await get().fetchProject(projectId);
    await get().fetchProjects();
  },

  removeFile: async (projectId, fileId) => {
    await api.deleteProjectFile(projectId, fileId);
    await get().fetchProject(projectId);
  },

  saveRules: async (projectId, rules) => {
    await api.saveProjectRules(projectId, rules);
    await get().fetchProject(projectId);
  },
}));

type AnalysisState = {
  activeCase: CaseResults | null;
  loading: boolean;
  progress: string | null;
  error: string | null;
  runAnalysis: (
    projectId: string,
    modules?: AnalysisModuleKey[],
    onProgress?: (partial: CaseResults) => void
  ) => Promise<CaseResults>;
  pollCase: (caseId: string, onProgress?: (partial: CaseResults) => void) => Promise<CaseResults>;
  clearAnalysis: () => void;
};

export const useAnalysisStore = create<AnalysisState>((set) => ({
  activeCase: null,
  loading: false,
  progress: null,
  error: null,

  runAnalysis: async (projectId, modules, onProgress) => {
    set({ loading: true, error: null, progress: "Starting analysis…", activeCase: null });
    try {
      const { case_id } = await api.analyzeProjectById(projectId, modules);
      const result = await api.pollCase(case_id, (partial) => {
        onProgress?.(partial);
        set({ activeCase: partial, progress: "Analysis in progress…" });
      });
      set({ activeCase: result, loading: false, progress: null });
      return result;
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "Analysis failed",
        loading: false,
        progress: null,
      });
      throw e;
    }
  },

  pollCase: async (caseId, onProgress) => {
    set({ loading: true, error: null });
    try {
      const result = await api.pollCase(caseId, onProgress);
      set({ activeCase: result, loading: false });
      return result;
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to load case", loading: false });
      throw e;
    }
  },

  clearAnalysis: () => set({ activeCase: null, loading: false, progress: null, error: null }),
}));
