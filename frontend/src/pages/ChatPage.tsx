import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Send, Loader2, Bot, User, Sparkles, Mail, CheckCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { joinWaitlist } from '../lib/api'
import type { ChatMessage } from '../types'

export default function ChatPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [showWaitlist, setShowWaitlist] = useState(false)
  const [waitlistEmail, setWaitlistEmail] = useState('')
  const [waitlistSubmitted, setWaitlistSubmitted] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const emailInputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, showWaitlist])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Waitlist mutation
  const waitlistMutation = useMutation({
    mutationFn: async (email: string) => {
      return joinWaitlist(email)
    },
    onSuccess: () => {
      setWaitlistSubmitted(true)
    },
  })

  // For beta - show waitlist instead of real AI
  const chatMutation = useMutation({
    mutationFn: async (_message: string) => {
      // Simulate a brief delay for natural feel
      await new Promise(resolve => setTimeout(resolve, 800))
      return { showWaitlist: true }
    },
    onSuccess: () => {
      setShowWaitlist(true)
      setTimeout(() => emailInputRef.current?.focus(), 100)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || chatMutation.isPending) return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    chatMutation.mutate(userMessage)
  }

  const handleWaitlistSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!waitlistEmail.trim() || waitlistMutation.isPending) return
    waitlistMutation.mutate(waitlistEmail.trim())
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
          {messages.length === 0 && !showWaitlist ? (
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

              {/* Waitlist CTA */}
              {showWaitlist && !waitlistSubmitted && (
                <div className="flex gap-3 justify-start">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center">
                    <Bot className="h-5 w-5 text-brand-600" />
                  </div>
                  <div className="bg-gradient-to-br from-brand-50 to-brand-100 rounded-2xl rounded-bl-md px-5 py-4 max-w-md border border-brand-200">
                    <p className="text-gray-800 mb-4">
                      We're launching personalized course planning to a small group of students first.
                      Join the list and we'll reach out within 24 hours to get you set up!
                    </p>
                    <form onSubmit={handleWaitlistSubmit} className="flex gap-2">
                      <div className="relative flex-1">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <input
                          ref={emailInputRef}
                          type="email"
                          required
                          value={waitlistEmail}
                          onChange={(e) => setWaitlistEmail(e.target.value)}
                          placeholder="your@email.com"
                          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 text-sm"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={waitlistMutation.isPending}
                        className={clsx(
                          'px-4 py-2 rounded-lg font-medium text-sm transition-colors',
                          waitlistMutation.isPending
                            ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                            : 'bg-brand-600 text-white hover:bg-brand-700'
                        )}
                      >
                        {waitlistMutation.isPending ? 'Joining...' : 'Join'}
                      </button>
                    </form>
                    {waitlistMutation.isError && (
                      <p className="text-red-500 text-sm mt-2">Something went wrong. Try again?</p>
                    )}
                  </div>
                </div>
              )}

              {/* Success state */}
              {waitlistSubmitted && (
                <div className="flex gap-3 justify-start">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  </div>
                  <div className="bg-green-50 rounded-2xl rounded-bl-md px-5 py-4 max-w-md border border-green-200">
                    <p className="text-green-800 font-medium">You're on the list!</p>
                    <p className="text-green-700 text-sm mt-1">
                      We'll reach out within 24 hours to help you plan the perfect semester.
                    </p>
                  </div>
                </div>
              )}
            </>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        {!showWaitlist && (
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
        )}
      </div>
    </div>
  )
}
