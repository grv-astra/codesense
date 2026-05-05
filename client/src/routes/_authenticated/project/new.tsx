// src/routes/_authenticated/project/new.tsx

import React, { useState } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { Input } from '@/components/atomic/input';
import type { CreateProjectDetails } from '@/types/project';
import { useCreateProject } from '@/hooks/use-project';
import { Card, CardHeader, CardTitle } from '@/components/atomic/card';
import { Info } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/atomic/tooltip';

export const Route = createFileRoute('/_authenticated/project/new')({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const createUserMutation = useCreateProject();
  const [formData, setFormData] = useState<CreateProjectDetails>({
    name: '',
    preset: '',
    description: ''
  });

  const [errors, setErrors] = useState<Partial<CreateProjectDetails>>({});

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
      }

      await createUserMutation.mutateAsync(projectData);

      setFormData({
        name: '',
        preset: '',
        description: ''
      })

      navigate({ from: '/project/new', to: '../list' });
    } catch (error) {
      console.error('Error creating user:', error);
    }
  };

  return (
    <div className="p-6 max-w-8xl mx-auto">
      <TooltipProvider>
        <Card>
          <CardHeader>
            <CardTitle className='text-2xl'>Create Project</CardTitle>
          </CardHeader>

          <form onSubmit={handleSubmit} className="space-y-6 px-6 pt-0">
            {/* Project Name */}
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <label className="block font-medium text-sm">Project Name</label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="w-3.5 h-3.5 text-muted-foreground cursor-pointer" />
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>Enter a unique name to identify your project.</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                className={`${errors.name ? 'border-destructive bg-destructive/10' : ''}`}
                placeholder="Enter project name"
              />
              {errors.name && <p className="text-sm text-red-600 mt-1">{errors.name}</p>}
            </div>

            {/* Preset */}
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <label className="block font-medium text-sm">Preset</label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="w-3.5 h-3.5 text-muted-foreground cursor-pointer" />
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>Enter a preset (type of project) template to configure default project settings.</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                name="preset"
                value={formData.preset}
                onChange={handleInputChange}
                placeholder="Enter Preset"
                className={`${errors.preset ? 'border-destructive bg-destructive/10' : ''}`}
              />
              {errors.preset && <p className="text-sm text-red-600 mt-1">{errors.preset}</p>}
            </div>

            {/* Description */}
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <label className="block font-medium text-sm">Description</label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="w-3.5 h-3.5 text-muted-foreground cursor-pointer" />
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>Briefly describe the purpose or scope of this project.</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                className={`${errors.description ? 'border-destructive bg-destructive/10' : ''}`}
                placeholder="Enter project description"
              />
              {errors.description && <p className="text-sm text-red-600 mt-1">{errors.description}</p>}
            </div>

            {/* Submit */}
            <div className='flex justify-center'>
              <button
                type="submit"
                className="px-6 bg-red-700 hover:bg-red-800 text-white font-semibold py-3 rounded shadow cursor-pointer"
              >
                <div className="flex items-center justify-center gap-2">
                  Create Project
                </div>
              </button>
            </div>
          </form>
        </Card>
      </TooltipProvider>
    </div>
  );
}