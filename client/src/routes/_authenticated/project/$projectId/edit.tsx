//edit

// src/routes/_authenticated/project/$projectId/edit.tsx

import React, { useState, useEffect } from 'react';
import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router';
import { Input } from '@/components/atomic/input';
import type { CreateProjectDetails } from '@/types/project';
import { useProjectDetails, useUpdateProject } from '@/hooks/use-project';
import { Card, CardHeader, CardTitle } from '@/components/atomic/card';
import { DotsLoader } from '@/components/atomic/loader';

export const Route = createFileRoute('/_authenticated/project/$projectId/edit')({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const { projectId } = useParams({ from: '/_authenticated/project/$projectId/edit' });
  const updateProjectMutation = useUpdateProject();
  const { data: project, isLoading, error } = useProjectDetails(projectId);

  const [formData, setFormData] = useState<CreateProjectDetails>({
    name: '',
    preset: '',
    description: ''
  });

  const [errors, setErrors] = useState<Partial<CreateProjectDetails>>({});

  // Populate form with existing project data
  useEffect(() => {
    if (project) {
      setFormData({
        name: project.name || '',
        preset: project.preset || '',
        description: project.description || ''
      });
    }
  }, [project]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    if (errors[name as keyof CreateProjectDetails]) {
      setErrors(prev => ({
        ...prev,
        [name]: undefined
      }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Partial<CreateProjectDetails> = {};
    if (!formData.name.trim()) newErrors.name = 'Project name is required';
    if (!formData.preset) newErrors.preset = 'Please select a preset';
    if (!formData.description.trim()) newErrors.description = 'Description is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;
    
    try {
      const projectData = {
        name: formData.name,
        preset: formData.preset,
        description: formData.description
      };

      await updateProjectMutation.mutateAsync({projectId, projectData});
      navigate({ from: '/project/$projectId/edit',  to: '../../list' });
    } catch (error) {
      console.error('Error updating project:', error);
    }
  };

  const handleCancel = () => {
    navigate({ to: '/project/list' });
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-8xl mx-auto">
        <DotsLoader />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-6 max-w-8xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle className='text-2xl text-red-600'>Error</CardTitle>
          </CardHeader>
          <div className="p-6">
            <p className="text-gray-600 mb-4">
              {error ? 'Failed to load project details.' : 'Project not found.'}
            </p>
            <button
              onClick={handleCancel}
              className="bg-gray-500 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded"
            >
              Back to Projects
            </button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-8xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle className='text-2xl'>Edit Project</CardTitle>
        </CardHeader>
        
        <form onSubmit={handleSubmit} className="space-y-6 px-6 pt-0 pb-6">
          {/* Project Name */}
          <div>
            <label className="block font-medium text-sm mb-1">Project Name</label>
            <Input
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              className={`${
                errors.name ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}
              placeholder="Enter project name"
            />
            {errors.name && <p className="text-sm text-red-600 mt-1">{errors.name}</p>}
          </div>

          {/* Preset */}
          <div>
            <label className="block font-medium text-sm mb-1">Preset</label>
            <Input
              name="preset"
              value={formData.preset}
              onChange={handleInputChange}
              placeholder="Enter Preset"
              className={`${
                errors.preset ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}
            />
            {errors.preset && <p className="text-sm text-red-600 mt-1">{errors.preset}</p>}
          </div>

          {/* Description */}
          <div>
            <label className="block font-medium text-sm mb-1">Description</label>
            <Input
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              className={`${
                errors.description ? 'border-red-500 bg-red-50' : 'border-gray-300'
              }`}              
              placeholder="Enter project description"
            />
            {errors.description && <p className="text-sm text-red-600 mt-1">{errors.description}</p>}
          </div>

          {/* Action Buttons */}
          <div className="flex gap-4">
            <button
              type="submit"
              disabled={updateProjectMutation.isPending}
              className="flex-1 bg-red-700 hover:bg-red-800 disabled:bg-red-400 text-white font-semibold py-3 rounded shadow cursor-pointer disabled:cursor-not-allowed"
            >
              <div className="flex items-center justify-center gap-2">
                {updateProjectMutation.isPending ? 'Updating...' : 'Update Project'}
              </div>
            </button>
            
            <button
              type="button"
              onClick={handleCancel}
              className="flex-1 bg-gray-500 hover:bg-gray-600 text-white font-semibold py-3 rounded shadow cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}