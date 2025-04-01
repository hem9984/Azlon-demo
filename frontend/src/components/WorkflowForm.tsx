import React, { useState } from 'react';
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";

// Define regex patterns to detect potentially harmful patterns
const PROHIBITED_PATTERNS = [
  /exec\s*\(/i,
  /eval\s*\(/i,
  /\bFunction\s*\(/i,
  /new\s+Function/i,
  /\bimport\s+/i,
  /\brequire\s*\(/i,
  /process\.env/i,
  /child_process/i,
  /\bfs\./i,
  /http\.request/i,
  /\bfetch\s*\(/i,
  /XMLHttpRequest/i,
  /\bajax\s*\(/i,
  /\bdocument\./i,
  /\bwindow\./i,
  /\blocation\./i,
  /\binject/i,
  /\bhack/i,
  /\bbypass/i,
  /\bexploit/i,
  /\bvulnerability/i
];

// Function to validate prompts
const validatePrompt = (prompt: string): { isValid: boolean, message?: string } => {
  // Check for suspicious patterns
  for (const pattern of PROHIBITED_PATTERNS) {
    if (pattern.test(prompt)) {
      return { 
        isValid: false,
        message: `Potentially unsafe pattern detected` 
      };
    }
  }
  
  // Check for excessively long prompts (to prevent prompt injection)
  if (prompt.length > 5000) {
    return {
      isValid: false,
      message: "Prompt is too long. Please keep prompts under 5000 characters."
    };
  }
  
  return { isValid: true };
};

interface WorkflowFormProps {
  userPrompt: string;
  setUserPrompt: (value: string) => void;
  testConditions: string;
  setTestConditions: (value: string) => void;
  advancedMode: boolean;
  setAdvancedMode: (value: boolean) => void;
  generateCodePrompt: string;
  setGenerateCodePrompt: (value: string) => void;
  validateOutputPrompt: string;
  setValidateOutputPrompt: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
}

const WorkflowForm = ({
  userPrompt,
  setUserPrompt,
  testConditions,
  setTestConditions,
  advancedMode,
  setAdvancedMode,
  generateCodePrompt,
  setGenerateCodePrompt,
  validateOutputPrompt,
  setValidateOutputPrompt,
  onSubmit,
  isLoading
}: WorkflowFormProps) => {
  const [validationErrors, setValidationErrors] = useState<{
    generateCode?: string;
    validateOutput?: string;
  }>({});
  
  // Handle form submission with validation
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Only validate in advanced mode
    if (advancedMode) {
      const generateCodeValidation = validatePrompt(generateCodePrompt);
      const validateOutputValidation = validatePrompt(validateOutputPrompt);
      
      const newErrors = {
        generateCode: !generateCodeValidation.isValid ? generateCodeValidation.message : undefined,
        validateOutput: !validateOutputValidation.isValid ? validateOutputValidation.message : undefined
      };
      
      setValidationErrors(newErrors);
      
      // Don't submit if there are errors
      if (newErrors.generateCode || newErrors.validateOutput) {
        return;
      }
    }
    
    onSubmit(e);
  };

  // Validate generate code prompt on change
  const handleGenerateCodePromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setGenerateCodePrompt(value);
    
    // Validate and update error state
    const validation = validatePrompt(value);
    if (!validation.isValid) {
      setValidationErrors(prev => ({
        ...prev,
        generateCode: validation.message
      }));
    } else {
      setValidationErrors(prev => ({
        ...prev,
        generateCode: undefined
      }));
    }
  };
  
  // Validate output validation prompt on change
  const handleValidateOutputPromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setValidateOutputPrompt(value);
    
    // Validate and update error state
    const validation = validatePrompt(value);
    if (!validation.isValid) {
      setValidationErrors(prev => ({
        ...prev,
        validateOutput: validation.message
      }));
    } else {
      setValidationErrors(prev => ({
        ...prev,
        validateOutput: undefined
      }));
    }
  };

  return (
    <Card className="p-6 card-glow">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center space-x-2">
            <Switch
              checked={advancedMode}
              onCheckedChange={setAdvancedMode}
              id="advanced-mode"
            />
            <Label htmlFor="advanced-mode">Advanced Mode</Label>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="user-prompt">User Prompt</Label>
            <Textarea
              id="user-prompt"
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              className="h-32 mt-2 textarea-code"
              placeholder="Write a Python script that prints 'hello world'"
            />
          </div>

          <div>
            <Label htmlFor="test-conditions">Test Conditions</Label>
            <Textarea
              id="test-conditions"
              value={testConditions}
              onChange={(e) => setTestConditions(e.target.value)}
              className="h-32 mt-2 textarea-code"
              placeholder="The script must print exactly 'hello world' and exit with code 0."
            />
          </div>

          {advancedMode && (
            <div className="space-y-4 animate-fade-in">
              <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
                <p className="text-sm text-yellow-700">
                  <strong>Warning:</strong> Advanced mode allows customizing model prompts.
                  Use with caution as improper prompts may lead to insecure code generation.
                </p>
              </div>
              
              <div>
                <Label htmlFor="generate-code-prompt">Generate Code Prompt</Label>
                <Textarea
                  id="generate-code-prompt"
                  value={generateCodePrompt}
                  onChange={handleGenerateCodePromptChange}
                  className={`h-48 mt-2 textarea-code ${validationErrors.generateCode ? 'border-red-500' : ''}`}
                />
                {validationErrors.generateCode && (
                  <p className="text-sm text-red-500 mt-1">{validationErrors.generateCode}</p>
                )}
              </div>

              <div>
                <Label htmlFor="validate-output-prompt">Validate Output Prompt</Label>
                <Textarea
                  id="validate-output-prompt"
                  value={validateOutputPrompt}
                  onChange={handleValidateOutputPromptChange}
                  className={`h-48 mt-2 textarea-code ${validationErrors.validateOutput ? 'border-red-500' : ''}`}
                />
                {validationErrors.validateOutput && (
                  <p className="text-sm text-red-500 mt-1">{validationErrors.validateOutput}</p>
                )}
              </div>
            </div>
          )}
        </div>

        <Button 
          type="submit" 
          className="w-full"
          disabled={isLoading || (advancedMode && (!!validationErrors.generateCode || !!validationErrors.validateOutput))}
        >
          {isLoading ? "Processing..." : "Run Workflow"}
        </Button>
      </form>
    </Card>
  );
};

export default WorkflowForm;