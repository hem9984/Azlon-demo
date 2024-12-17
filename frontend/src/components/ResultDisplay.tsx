import React from 'react';
import { Card } from "@/components/ui/card";

interface ResultDisplayProps {
  result: any;
}

const ResultDisplay = ({ result }: ResultDisplayProps) => {
  if (!result) return null;

  return (
    <Card className="p-6 mt-6 card-glow">
      <h2 className="text-xl font-semibold mb-4">Result</h2>
      <pre className="bg-secondary p-4 rounded-lg overflow-x-auto textarea-code">
        {JSON.stringify(result, null, 2)}
      </pre>
    </Card>
  );
};

export default ResultDisplay;