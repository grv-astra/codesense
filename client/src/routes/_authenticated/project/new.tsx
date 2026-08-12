// src/routes/_authenticated/project/new.tsx

import React, { useState } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { Input } from '@/components/atomic/input';
import type { CreateProjectDetails } from '@/types/project';
import { useCreateProject } from '@/hooks/use-project';
import { Card } from '@/components/atomic/card';
import { AlertCircle, CheckCircle2, FolderPlus, Info } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/atomic/tooltip';

export const Route = createFileRoute('/_authenticated/project/new')({
  component: RouteComponent,
});

function StepBadge({ step }: { step: number }) {
  return (
    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-medium bg-gray-100 dark:bg-white/10 text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-white/10 flex-shrink-0">
      {step}
    </span>
  );
}

function SectionHeading({ step, title }: { step: number; title: string }) {
  return (
    <div className="flex items-center gap-2.5 mb-4">
      <StepBadge step={step} />
      <span className="text-[13px] font-medium text-gray-700 dark:text-gray-300">{title}</span>
      <div className="flex-1 border-t border-gray-100 dark:border-white/10" />
    </div>
  );
}

function FieldLabel({ children, tooltip }: { children: React.ReactNode; tooltip?: string }) {
  return (
    <div className="flex items-center gap-1.5 mb-1.5">
      <label className="block text-[11px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500">
        {children}
      </label>
      {tooltip && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="w-3 h-3 text-gray-400 dark:text-gray-500 cursor-pointer" />
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}

function ErrorText({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p className="flex items-center gap-1.5 text-[12px] text-red-600 dark:text-red-400 mt-1.5">
      <AlertCircle size={12} />
      {message}
    </p>
  );
}

function RouteComponent() {
  const navigate = useNavigate();
  const createProjectMutation = useCreateProject();
  const [formData, setFormData] = useState<CreateProjectDetails>({
    name: '',
    preset: '',
    description: '',
  });
  const [errors, setErrors] = useState<Partial<CreateProjectDetails>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name as keyof CreateProjectDetails]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
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
    setIsSubmitting(true);
    try {
      await createProjectMutation.mutateAsync({
        name: formData.name,
        preset: formData.preset,
        description: formData.description,
      });
      setSubmitted(true);
      setFormData({ name: '', preset: '', description: '' });
      setTimeout(() => {
        navigate({ from: '/project/new', to: '../list' });
      }, 800);
    } catch (error) {
      console.error('Error creating project:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <TooltipProvider>
      <div className="min-h-screen p-8">
        <div className="max-w-8xl mx-auto">
          <Card className="border shadow-sm rounded-xl overflow-hidden">
            {/* Page heading */}
            <div className="px-6">
              <div className="flex items-center gap-2 text-[12px] mb-3 font-medium uppercase tracking-widest">
                <span>Projects</span>
                <span>/</span>
                <span>New project</span>
              </div>
              <h1 className="text-[22px] font-semibold text-gray-900 dark:text-white leading-tight">
                Create a new project
              </h1>
              <p className="text-[14px] mt-1">
                Give your project a name and a bit of context to get started.
              </p>
            </div>

            {/* Card top accent bar */}
            <div className="h-[3px] w-full bg-gradient-to-r from-[#bf0000] via-[#e03030] to-[#ff6060]" />

            <form onSubmit={handleSubmit} noValidate>
              <div className="px-7 py-6 space-y-7">
                <section>
                  <SectionHeading step={1} title="Project details" />

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <FieldLabel tooltip="Enter a unique name to identify your project.">
                        Project name
                      </FieldLabel>
                      <Input
                        name="name"
                        value={formData.name}
                        onChange={handleInputChange}
                        placeholder="Enter project name"
                        className={[
                          'h-10 text-[14px]',
                          errors.name ? 'border-red-500 dark:border-red-500 bg-red-50 dark:bg-red-900/10' : '',
                        ].join(' ')}
                      />
                      <ErrorText message={errors.name} />
                    </div>

                    <div>
                      <FieldLabel tooltip="Enter a preset (type of project) template to configure default project settings.">
                        Preset
                      </FieldLabel>
                      <Input
                        name="preset"
                        value={formData.preset}
                        onChange={handleInputChange}
                        placeholder="Enter preset"
                        className={[
                          'h-10 text-[14px]',
                          errors.preset ? 'border-red-500 dark:border-red-500 bg-red-50 dark:bg-red-900/10' : '',
                        ].join(' ')}
                      />
                      <ErrorText message={errors.preset} />
                    </div>
                  </div>

                  <div className="mt-4">
                    <FieldLabel tooltip="Briefly describe the purpose or scope of this project.">
                      Description
                    </FieldLabel>
                    <Input
                      name="description"
                      value={formData.description}
                      onChange={handleInputChange}
                      placeholder="Enter project description"
                      className={[
                        'h-10 text-[14px]',
                        errors.description ? 'border-red-500 dark:border-red-500 bg-red-50 dark:bg-red-900/10' : '',
                      ].join(' ')}
                    />
                    <ErrorText message={errors.description} />
                  </div>
                </section>
              </div>

              {/* Footer */}
              <div className="px-7 py-4 border-t border-gray-100 dark:border-white/[0.07] flex items-center justify-between gap-4">
                <div className="text-[12px] text-gray-400 dark:text-gray-500">
                  All fields are required to create a project.
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting || submitted}
                  className={[
                    'inline-flex items-center gap-2 px-5 h-10 rounded-lg text-[13px] font-semibold transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#bf0000]',
                    submitted
                      ? 'bg-emerald-600 text-white cursor-default'
                      : isSubmitting
                      ? 'bg-[#bf0000]/70 text-white cursor-wait'
                      : 'bg-[#bf0000] hover:bg-[#a00000] active:scale-[0.98] text-white shadow-sm shadow-red-900/20',
                  ].join(' ')}
                >
                  {submitted ? (
                    <>
                      <CheckCircle2 size={15} />
                      Project created
                    </>
                  ) : isSubmitting ? (
                    <>
                      <svg
                        className="animate-spin"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                      >
                        <circle
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="3"
                          strokeDasharray="40"
                          strokeDashoffset="15"
                          strokeLinecap="round"
                        />
                      </svg>
                      Creating…
                    </>
                  ) : (
                    <>
                      <FolderPlus size={14} />
                      Create project
                    </>
                  )}
                </button>
              </div>
            </form>
          </Card>

          {/* Footer note */}
          <p className="text-center text-[12px] text-gray-400 dark:text-gray-600 mt-5">
            Projects group your scans together — you can start scanning right after creating one.
          </p>
        </div>
      </div>
    </TooltipProvider>
  );
}
