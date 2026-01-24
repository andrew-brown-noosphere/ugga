import { useState, useRef, useEffect } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { useMutation } from '@tanstack/react-query'
import { MessageCircle, X, Send, Loader2, Bot, User, Sparkles, ExternalLink, LogIn } from 'lucide-react'
import { clsx } from 'clsx'
import { sendChatMessage, setAuthToken } from '../lib/api'
import type { ChatMessage, ChatSource } from '../types'

interface ChatPanelProps {
  className?: string
}

export default function ChatPanel({ className }: ChatPanelProps) {
  const { getToken, isSignedIn } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sources, setSources] = useState<ChatSource[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      // Set auth token if signed in for personalized responses
      if (isSignedIn) {
        const token = await getToken()
        setAuthToken(token)
      } else {
        setAuthToken(null)
      }
      return sendChatMessage(message, messages)
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.answer },
      ])
      setSources(data.sources)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || chatMutation.isPending) return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setSources([])
    chatMutation.mutate(userMessage)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  // Different suggestions based on auth status
  const suggestedQuestions = isSignedIn
    ? [
        "What should I take next semester?",
        "Am I on track to graduate?",
        "What requirements do I have left?",
      ]
    : [
        "What courses cover machine learning?",
        "Easy electives for CS majors?",
        "Prerequisites for CSCI 4720?",
      ]

  return (
    <>
      {/* Floating Chat Button */}
      <button
        onClick={() => setIsOpen(true)}
        className={clsx(
          'fixed bottom-6 right-6 z-40 p-4 rounded-full shadow-lg transition-all duration-300',
          'bg-gradient-to-br from-brand-600 to-brand-700 text-white',
          'hover:shadow-xl hover:scale-105',
          isOpen && 'hidden',
          className
        )}
        aria-label="Open AI Chat"
      >
        <MessageCircle className="h-6 w-6" />
      </button>

      {/* Chat Panel */}
      <div
        className={clsx(
          'fixed bottom-6 right-6 z-50 w-96 max-h-[600px] rounded-2xl shadow-2xl',
          'bg-white border border-gray-200 flex flex-col overflow-hidden',
          'transition-all duration-300 transform',
          isOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'
        )}
      >
        {/* Header */}
        <div className="bg-gradient-to-br from-brand-600 to-brand-700 px-4 py-3 text-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-white/20 rounded-lg">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">AI Academic Advisor</h3>
              <p className="text-white/70 text-xs">
                {isSignedIn
                  ? "Personalized to your courses & progress"
                  : "Ask about courses, programs, and planning"}
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 rounded-full hover:bg-white/20 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[300px] max-h-[400px]">
          {messages.length === 0 ? (
            <div className="text-center py-8">
              <Bot className="h-12 w-12 mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500 text-sm mb-4">
                {isSignedIn
                  ? "I know your courses and progress. Ask me anything!"
                  : "Ask me anything about UGA courses, programs, or academic planning."}
              </p>
              {!isSignedIn && (
                <div className="mb-4 px-3 py-2 bg-brand-50 border border-brand-200 rounded-lg">
                  <p className="text-xs text-brand-700 flex items-center justify-center gap-1">
                    <LogIn className="h-3 w-3" />
                    Sign in for personalized recommendations
                  </p>
                </div>
              )}
              <div className="space-y-2">
                <p className="text-xs text-gray-400">Try asking:</p>
                {suggestedQuestions.map((q) => (
                  <button
                    key={q}
                    onClick={() => {
                      setInput(q)
                      inputRef.current?.focus()
                    }}
                    className="block w-full text-left px-3 py-2 text-sm text-gray-600 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={i}
                className={clsx(
                  'flex gap-2',
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                {msg.role === 'assistant' && (
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-brand-600" />
                  </div>
                )}
                <div
                  className={clsx(
                    'max-w-[80%] rounded-2xl px-4 py-2 text-sm',
                    msg.role === 'user'
                      ? 'bg-brand-600 text-white rounded-br-md'
                      : 'bg-gray-100 text-gray-800 rounded-bl-md'
                  )}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
                {msg.role === 'user' && (
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center">
                    <User className="h-4 w-4 text-gray-600" />
                  </div>
                )}
              </div>
            ))
          )}

          {chatMutation.isPending && (
            <div className="flex gap-2 justify-start">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center">
                <Bot className="h-4 w-4 text-brand-600" />
              </div>
              <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
                <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
              </div>
            </div>
          )}

          {chatMutation.isError && (
            <div className="text-center py-2">
              <p className="text-red-500 text-sm">
                Sorry, something went wrong. Please try again.
              </p>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Sources */}
        {sources.length > 0 && (
          <div className="px-4 py-2 border-t bg-gray-50">
            <p className="text-xs text-gray-500 mb-1">Sources:</p>
            <div className="flex flex-wrap gap-1">
              {sources.slice(0, 5).map((source, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-white border border-gray-200 rounded text-xs text-gray-600"
                >
                  {source.code || source.title}
                  {source.type === 'course' && (
                    <ExternalLink className="h-3 w-3 text-gray-400" />
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <form onSubmit={handleSubmit} className="p-3 border-t bg-white">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about courses, programs..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
            <button
              type="submit"
              disabled={!input.trim() || chatMutation.isPending}
              className={clsx(
                'p-2.5 rounded-xl transition-colors',
                input.trim() && !chatMutation.isPending
                  ? 'bg-brand-600 text-white hover:bg-brand-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              )}
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
          <p className="text-[10px] text-gray-400 mt-1.5 text-center">
            AI responses are based on UGA course data. Verify with your advisor.
          </p>
        </form>
      </div>
    </>
  )
}
