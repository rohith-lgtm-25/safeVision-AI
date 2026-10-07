import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Upload, Loader2 } from 'lucide-react';
import { API_BASE } from '../config';

const ImageDetection: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [resultImage, setResultImage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setResultImage(null);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post(`${API_BASE}/detect/image`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.status === 'success') {
        setResultImage(response.data.image);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'An error occurred during processing.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Upload Image for Detection</h3>
        
        <div className="flex items-center justify-center w-full">
          <label className="flex flex-col items-center justify-center w-full h-64 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100">
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <Upload className="w-10 h-10 mb-3 text-gray-400" />
              <p className="mb-2 text-sm text-gray-500"><span className="font-semibold">Click to upload</span> or drag and drop</p>
              <p className="text-xs text-gray-500">PNG, JPG or JPEG (MAX. 5MB)</p>
            </div>
            <input 
              ref={fileInputRef}
              type="file" 
              className="hidden" 
              accept="image/*"
              onChange={handleFileChange}
            />
          </label>
        </div>

        {selectedFile && (
          <div className="mt-4 flex justify-between items-center bg-gray-50 p-4 rounded-md">
            <span className="text-sm text-gray-700 truncate">{selectedFile.name}</span>
            <button
              onClick={handleUpload}
              disabled={isProcessing}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                'Run Detection'
              )}
            </button>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 text-sm text-red-700 bg-red-100 rounded-md">
            {error}
          </div>
        )}
      </div>

      {(previewUrl || resultImage) && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Results</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Original</p>
              <img src={previewUrl!} alt="Original" className="w-full h-auto rounded-lg border border-gray-200" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Processed</p>
              {resultImage ? (
                <img src={resultImage} alt="Result" className="w-full h-auto rounded-lg border border-gray-200" />
              ) : (
                <div className="w-full h-full min-h-[200px] flex items-center justify-center bg-gray-100 rounded-lg border border-gray-200">
                  <span className="text-gray-400 text-sm">Processing...</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageDetection;
