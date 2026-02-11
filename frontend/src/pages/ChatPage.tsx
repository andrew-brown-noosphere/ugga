import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useAuth } from '@clerk/clerk-react'
import { Send, Loader2, Bot, User, Sparkles, AlertCircle, MessageCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { sendChatMessage, setAuthToken } from '../lib/api'
import type { ChatMessage } from '../types'
import AuthGate from '../components/AuthGate'

const CHAT_FEATURES = [
  'Get personalized course recommendations based on your goals',
  'Ask questions about degree requirements and prerequisites',
  'Find the best professors and sections for your schedule',
  'Plan your entire semester with AI-powered insights',
]

export default function ChatPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const { getToken } = useAuth()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Real AI chat mutation
  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      // Set auth token for the request
      const token = await getToken()
      setAuthToken(token)

      // Send message with conversation history
      return sendChatMessage(message, messages)
    },
    onSuccess: (response) => {
      setError(null)
      // Add assistant response to messages
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.answer },
      ])
    },
    onError: (err: Error) => {
      // Show error message
      const errorMessage = err.message?.includes('503')
        ? 'AI chat is temporarily unavailable. Please try again later.'
        : 'Something went wrong. Please try again.'
      setError(errorMessage)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || chatMutation.isPending) return

    const userMessage = input.trim()
    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    chatMutation.mutate(userMessage)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const suggestedQuestions = [
    "What should I take next semester?",
    "Help me find easy electives",
    "How do I balance my schedule?",
    "Which professors are best?",
  ]

  return (
    <AuthGate
      icon={MessageCircle}
      title="AI Course Advisor"
      description="Get personalized course recommendations and degree planning help"
      features={CHAT_FEATURES}
    >
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-600 to-brand-700 mb-4">
          <Sparkles className="h-8 w-8 text-white" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Plan Your Semester</h1>
        <p className="text-gray-600">
          Get personalized course recommendations and degree planning help.
        </p>
      </div>

      {/* Chat Container */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
        {/* Messages */}
        <div className="h-[500px] overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <Bot className="h-16 w-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500 mb-6">Start by asking a question about your courses</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg mx-auto">
                {suggestedQuestions.map((q) => (
                  <button
                    key={q}
                    onClick={() => {
                      setInput(q)
                      inputRef.current?.focus()
                    }}
                    className="text-left px-4 py-3 text-sm text-gray-600 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors border border-gray-200"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={clsx(
                    'flex gap-3',
                    msg.role === 'user' ? 'justify-end' : 'justify-start'
                  )}
                >
                  {msg.role === 'assistant' && (
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center">
                      <Bot className="h-5 w-5 text-brand-600" />
                    </div>
                  )}
                  <div
                    className={clsx(
                      'max-w-[70%] rounded-2xl px-5 py-3',
                      msg.role === 'user'
                        ? 'bg-brand-600 text-white rounded-br-md'
                        : 'bg-gray-100 text-gray-800 rounded-bl-md'
                    )}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                  {msg.role === 'user' && (
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center">
                      <User className="h-5 w-5 text-gray-600" />
                    </div>
                  )}
                </div>
              ))}

              {chatMutation.isPending && (
                <div className="flex gap-3 justify-start">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center">
                    <Bot className="h-5 w-5 text-brand-600" />
                  </div>
                  <div className="bg-gray-100 rounded-2xl rounded-bl-md px-5 py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-gray-500" />
                  </div>
                </div>
              )}

              {/* Error state */}
              {error && (
                <div className="flex gap-3 justify-start">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                    <AlertCircle className="h-5 w-5 text-red-600" />
                  </div>
                  <div className="bg-red-50 rounded-2xl rounded-bl-md px-5 py-4 max-w-md border border-red-200">
                    <p className="text-red-800">{error}</p>
                    <button
                      onClick={() => setError(null)}
                      className="text-red-600 text-sm mt-2 hover:underline"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="p-4 border-t bg-white">
          <div className="flex gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about courses, programs, professors..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
            <button
              type="submit"
              disabled={!input.trim() || chatMutation.isPending}
              className={clsx(
                'px-5 py-3 rounded-xl transition-colors font-medium',
                input.trim() && !chatMutation.isPending
                  ? 'bg-brand-600 text-white hover:bg-brand-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              )}
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
        </form>
      </div>
    </div>
    </AuthGate>
  )
}
