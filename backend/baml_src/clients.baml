// Learn more about clients at https://docs.boundaryml.com/docs/snippets/clients/overview

client<llm> DeepseekR1_14b {
  provider ollama
  options {
    model deepseek-r1:14b
    base_url "http://local-llm:11434/v1"
    headers {
      allowed_role_metadata "autonomous coding agent"
    }
  }
}

client<llm> Llama3 {
  provider ollama
  options {
    model llama3
    base_url "http://local-llm:11434/v1"
    headers {
      allowed_role_metadata "autonomous coding agent"
    }
  }
}

client<llm> Qwen2_5 {
  provider ollama
  options {
    model qwen2.5
    base_url "http://local-llm:11434/v1"
    headers {
      allowed_role_metadata "autonomous coding agent"
    }
  }
}

client<llm> DeepseekR1_8b {
  provider ollama
  options {
    model deepseek-r1:8b
    base_url "http://local-llm:11434/v1"
    headers {
      allowed_role_metadata "autonomous coding agent"
    }
  }
}

client<llm> DeepseekR1 {
  provider ollama
  options {
    model deekseek-r1
    base_url "http://local-llm:11434/v1"
    headers {
      allowed_role_metadata "autonomous coding agent"
    }
  }
}

template_string Foo() #"
  {{ _.role('user') }}
  This will be have foo and bar, but not cat metadata. But only for Foo, not FooWithout.
  {{ _.role('user') }}
  This will have none of the role metadata for Foo or FooWithout.
"#


client<llm> CustomGPT4o {
  provider openai
  options {
    model "gpt-4o"
    api_key env.OPENAI_KEY
  }
}

client<llm> CustomGPT4oMini {
  provider openai
  retry_policy Exponential
  options {
    model "gpt-4o-mini"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> CustomSonnet {
  provider anthropic
  options {
    model "claude-3-5-sonnet-20241022"
    api_key env.ANTHROPIC_API_KEY
  }
}


client<llm> CustomHaiku {
  provider anthropic
  retry_policy Constant
  options {
    model "claude-3-haiku-20240307"
    api_key env.ANTHROPIC_API_KEY
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/round-robin
client<llm> CustomFast {
  provider round-robin
  options {
    // This will alternate between the two clients
    strategy [CustomGPT4oMini, CustomHaiku]
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/fallback
client<llm> OpenaiFallback {
  provider fallback
  options {
    // This will try the clients in order until one succeeds
    strategy [CustomGPT4oMini, CustomGPT4oMini]
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/retry
retry_policy Constant {
  max_retries 3
  // Strategy is optional
  strategy {
    type constant_delay
    delay_ms 200
  }
}

retry_policy Exponential {
  max_retries 2
  // Strategy is optional
  strategy {
    type exponential_backoff
    delay_ms 300
    mutliplier 1.5
    max_delay_ms 10000
  }
}