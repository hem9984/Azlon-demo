import React, { useState, useEffect } from 'react';
import { useToast } from "@/components/ui/use-toast";
import WorkflowForm from '@/components/WorkflowForm';
import ResultDisplay from '@/components/ResultDisplay';

const API_URL = "http://localhost:3000";

const Index = () => {
  const [userPrompt, setUserPrompt] = useState("");
  const [testConditions, setTestConditions] = useState("");
  const [advancedMode, setAdvancedMode] = useState(false);
  const [generateCodePrompt, setGenerateCodePrompt] = useState("");
  const [validateOutputPrompt, setValidateOutputPrompt] = useState("");
  const [result, setResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    console.log("Advanced mode toggled:", advancedMode);
    if (advancedMode) {
      fetchPrompts();
    }
  }, [advancedMode]);

  const fetchPrompts = async () => {
    try {
      console.log("Fetching prompts...");
      const response = await fetch(`${API_URL}/prompts`);
      const data = await response.json();
      console.log("Fetched prompts:", data);
      setGenerateCodePrompt(data.generate_code_prompt);
      setValidateOutputPrompt(data.validate_output_prompt);
    } catch (error) {
      console.error("Error fetching prompts:", error);
      toast({
        title: "Error",
        description: "Failed to fetch prompts. Please try again.",
        variant: "destructive",
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    console.log("Submitting workflow...");

    try {
      if (advancedMode) {
        console.log("Updating prompts...");
        await fetch(`${API_URL}/prompts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            generate_code_prompt: generateCodePrompt,
            validate_output_prompt: validateOutputPrompt
          })
        });
      }

      console.log("Running workflow...");
      const response = await fetch(`${API_URL}/run_workflow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_prompt: userPrompt,
          test_conditions: testConditions
        })
      });

      const data = await response.json();
      console.log("Workflow result:", data);
      setResult(data);
      toast({
        title: "Success",
        description: "Workflow completed successfully.",
      });
    } catch (error) {
      console.error("Error running workflow:", error);
      toast({
        title: "Error",
        description: "Failed to run workflow. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen gradient-bg py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-center mb-8 bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-600">
          Azlon-Demo
        </h1>
        
        <WorkflowForm
          userPrompt={userPrompt}
          setUserPrompt={setUserPrompt}
          testConditions={testConditions}
          setTestConditions={setTestConditions}
          advancedMode={advancedMode}
          setAdvancedMode={setAdvancedMode}
          generateCodePrompt={generateCodePrompt}
          setGenerateCodePrompt={setGenerateCodePrompt}
          validateOutputPrompt={validateOutputPrompt}
          setValidateOutputPrompt={setValidateOutputPrompt}
          onSubmit={handleSubmit}
          isLoading={isLoading}
        />

        <ResultDisplay result={result} />
      </div>
    </div>
  );
};

export default Index;
