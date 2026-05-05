import { Card, CardHeader, CardTitle } from '@/components/atomic/card';
import { Input } from '@/components/atomic/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/atomic/select';
import { useProjectNames } from '@/hooks/use-project';
import { useSbomScan } from '@/hooks/use-scans';
import type { CreateSBOMScanForm } from '@/types/scan';
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { FolderOpen, Play, Upload, X } from 'lucide-react';
import React, { useState } from 'react';

export const Route = createFileRoute('/_authenticated/scan/start/kuchbhi')({
  component: RouteComponent,
})

function RouteComponent() {
  const navigate = useNavigate()
  const createScanMutation = useSbomScan();
  const [formData, setFormData] = useState<CreateSBOMScanForm>({
    scan_name: '',
    file: null,
    project_id: '',
  });

  const {data: projects =[] } = useProjectNames()
  const [isDragOver, setIsDragOver] = useState(false);
  const [errors, setErrors] = useState<Partial<CreateSBOMScanForm>>({});

  const handleSelectChange = (value: string) => {
    setFormData(prev => ({
      ...prev,
      project_id: value,
    }));
    if (errors.project_id) {
      setErrors(prev => ({
        ...prev,
        project_id: undefined,
      }));
    }
  };

   const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const { name, value } = e.target;
      setFormData(prev => ({ ...prev, [name]: value }));
      if (errors[name as keyof CreateSBOMScanForm]) {
        setErrors(prev => ({ ...prev, [name]: undefined }));
      }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        console.log(file?.type)
        if (file) {
          if (file.type === 'application/json' || file.name.endsWith('.json')) {
            setFormData(prev => ({ ...prev, file: file }));
            setErrors(prev => ({ ...prev, file_error: undefined }));
          } else {
            setErrors(prev => ({ ...prev, file_error: "Please upload a valid SBOM-json file" }));
          }
        }
      };

    const handleDragOver = (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(true);
    };
  
    const handleDragLeave = (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
    };
  
    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        if (file.type === 'application/json' || file.name.endsWith('.json')) {
          setFormData(prev => ({ ...prev,  file: file }));
          setErrors(prev => ({ ...prev, file_error: undefined }));
        } else {
          setErrors(prev => ({ ...prev, file_error: 'Please upload a valid SBOM-json file' }));
        }
      }
    };

      const removeFile = () => {
        setFormData(prev => ({ ...prev, file: null }));
      };
    
      const validateForm = (): boolean => {
        const newErrors: Partial<CreateSBOMScanForm> = {};
        if (!formData.project_id.trim()) newErrors.project_id = 'Project selection is required';
        if (!formData.scan_name.trim()) newErrors.scan_name = 'Scan name is required';
        if (!formData.file) newErrors.file_error = 'Please upload a valid SBOM-json file';
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
      };
    
      const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
          if (validateForm()) {
            const scanData = {
              scan_name: formData.scan_name,
              project_id: formData.project_id,
              file: formData.file,
            }
            console.log('Form submitted:', scanData);
            
            await createScanMutation.mutateAsync(scanData);
          }
    
          setFormData({
            scan_name: '',
            project_id: '',
            file: null,
          })
    
          navigate({ from: '/scan/start', to: `../../project/${formData.project_id}` });
        } catch (error) {
          console.error('Error creating user:', error);
        }
        
      };
  
  return ( 
  <>
    <div className="p-6 max-w-8xl mx-auto">
        <Card className="bg-white dark:bg-[#2d2d2d] text-[#2d2d2d] dark:text-[#e5e5e5] shadow-lg rounded-lg">
          <CardHeader>
            <CardTitle className='text-2xl'>Start SBOM Scan</CardTitle>
          </CardHeader>
          <form onSubmit={handleSubmit} className="space-y-6 px-6 pt-0">
            <div>
              <label className='block font-medium text-sm mb-1'>Select Project</label>
              <Select value={formData.project_id} onValueChange={handleSelectChange}>
                <SelectTrigger className={`w-full p-3 rounded bg-white dark:bg-[#2d2d2d] text-[#2d2d2d] dark:text-[#e5e5e5] 
                  ${errors.project_id ? 'border-red-500 bg-red-50 dark:bg-[#3b1c1c]' : 'border border-gray-300 dark:border-gray-200/20'}`}
                >
                  <SelectValue placeholder="Select a project" />
                </SelectTrigger>
                <SelectContent className='bg-white dark:bg-[#2d2d2d] text-[#2d2d2d] dark:text-[#e5e5e5]'>
                  {projects.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.project_id && (
                <p className="text-sm text-red-600 mt-1">{errors.project_id}</p>
              )}
            </div>

            {/* scan Name input */}
            <div>
              <label className="block font-medium text-sm mb-1"> Scan Name</label>
              <Input 
                name="scan_name"
                value={formData.scan_name}
                onChange={handleInputChange}
                className={`${errors.scan_name && 'border-red-500 bg-red-50 dark:bg-[#3b1c1c]'}`}
                placeholder="Enter scan name"
              />
              {errors.scan_name && <p className="text-sm text-red-600 mt-1">{errors.scan_name}</p>}
            </div>

            <div>
            <label className="block font-medium text-sm mb-1">SBOM File</label>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-lg p-6 ${ isDragOver || errors.file_error && 'border-red-500 bg-red-50 dark:bg-[#3b1c1c]'}`}
            >
              <input
                type="file"
                accept=".json"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              {formData.file ? (
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <FolderOpen className="text-red-600" />
                    <div>
                      <p>{formData.file.name}</p>
                      <p className="text-xs text-gray-500">{(formData.file.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                  </div>
                  <button type="button" onClick={removeFile} className="text-red-600 hover:text-red-800">
                    <X />
                  </button>
                </div>
              ) : (
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <Upload className="mx-auto mb-2" />
                  Drag and drop or click to upload json file
                </div>
              )}
            </div>
            {errors.file_error && <p className="text-sm text-red-600 mt-1">{errors.file_error}</p>}
          </div>

          {/* Submit Button */}
          <div className='flex justify-center'>
            <button
              type="submit"
              className="px-6 bg-[#bf0000] hover:bg-red-800 text-white font-semibold py-3 rounded shadow"
            >
              <div className="flex items-center justify-center gap-2">
                <Play size={16} />
                Start Scan
              </div>
            </button>
          </div>

          </form>
        </Card>
    </div>
  </>
);
}

export default RouteComponent;