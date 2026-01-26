import { useState, useRef, useEffect } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { useMutation } from '@tanstack/react-query'
import { Send, Loader2, Bot, User, Sparkles, ExternalLink, LogIn } from 'lucide-react'
import { clsx } from 'clsx'
import { sendChatMessage, setAuthToken } from '../lib/api'
import type { ChatMessage, ChatSource } from '../types'

export default function ChatPage() {
  const { getToken, isSignedIn } = useAuth()
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
    inputRef.current?.focus()
  }, [])

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
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

  const suggestedQuestions = isSignedIn
    ? [
        "What should I take next semester?",
        "Am I on track to graduate?",
        "What requirements do I have left?",
        "Which professors are best for my major?",
      ]
    : [
        "What courses cover machine learning?",
        "Easy electives for CS majors?",
        "Prerequisites for CSCI 4720?",
        "Best professors for intro CS?",
      ]

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-600 to-brand-700 mb-4">
          <Sparkles className="h-8 w-8 text-white" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">AI Academic Advisor</h1>
        <p className="text-gray-600">
          {isSignedIn
            ? "I know your courses and progress. Ask me anything!"
            : "Ask me about UGA courses, programs, and academic planning."}
        </p>
        {!isSignedIn && (
          <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-brand-50 border border-brand-200 rounded-lg">
            <LogIn className="h-4 w-4 text-brand-600" />
            <span className="text-sm text-brand-700">Sign in for personalized recommendations</span>
          </div>
        )}
      </div>

      {/* Chat Container */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
        {/* Messages */}
        <div className="h-[500px] overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <Bot className="h-16 w-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500 mb-6">Start a conversation by asking a question</p>
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
            messages.map((msg, i) => (
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
            ))
          )}

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

          {chatMutation.isError && (
            <div className="text-center py-4">
              <p className="text-red-500">Sorry, something went wrong. Please try again.</p>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Sources */}
        {sources.length > 0 && (
          <div className="px-6 py-3 border-t bg-gray-50">
            <p className="text-sm text-gray-500 mb-2">Sources:</p>
            <div className="flex flex-wrap gap-2">
              {sources.slice(0, 8).map((source, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 px-3 py-1 bg-white border border-gray-200 rounded-lg text-sm text-gray-600"
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
          <p className="text-xs text-gray-400 mt-2 text-center">
            AI responses are based on UGA course data. Always verify with your academic advisor.
          </p>
        </form>
      </div>
    </div>
  )
}
