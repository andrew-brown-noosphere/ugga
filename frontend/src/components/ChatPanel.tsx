import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { MessageCircle, X, Send, Loader2, Bot, User, Sparkles, Mail, CheckCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { joinWaitlist } from '../lib/api'
import type { ChatMessage } from '../types'

interface ChatPanelProps {
  className?: string
}

export default function ChatPanel({ className }: ChatPanelProps) {
  const [isOpen, setIsOpen] = useState(false)
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
  }, [messages])

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  // Waitlist mutation
  const waitlistMutation = useMutation({
    mutationFn: async (email: string) => {
      return joinWaitlist(email)
    },
    onSuccess: () => {
      setWaitlistSubmitted(true)
    },
  })

  // For now, always show waitlist instead of real AI (beta mode)
  const chatMutation = useMutation({
    mutationFn: async (_message: string) => {
      // Simulate a brief delay for natural feel
      await new Promise(resolve => setTimeout(resolve, 800))
      // Don't actually call AI - just trigger waitlist flow
      return { showWaitlist: true }
    },
    onSuccess: () => {
      setShowWaitlist(true)
      // Focus email input after a brief delay
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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  // Suggested questions to get users engaged
  const suggestedQuestions = [
    "What courses should I take next semester?",
    "Help me find easy electives",
    "How do I balance my schedule?",
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
              <h3 className="font-semibold text-sm">Plan Your Semester</h3>
              <p className="text-white/70 text-xs">
                Your friendly guide to the perfect schedule
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
          {messages.length === 0 && !showWaitlist ? (
            <div className="text-center py-8">
              <Bot className="h-12 w-12 mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500 text-sm mb-4">
                Hey! I'm here to help you plan the perfect semester. Ask me anything!
              </p>
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
            <>
              {/* Show user's message */}
              {messages.map((msg, i) => (
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
              ))}

              {/* Loading state */}
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

              {/* Waitlist CTA */}
              {showWaitlist && !waitlistSubmitted && (
                <div className="flex gap-2 justify-start">
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-brand-600" />
                  </div>
                  <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-gray-100 px-4 py-3">
                    <p className="text-sm text-gray-800 mb-3">
                      Great question! 🎓 We're currently in private beta with limited spots.
                    </p>
                    <p className="text-sm text-gray-800 mb-4">
                      Join our waitlist and we'll get you set up soon!
                    </p>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault()
                        if (waitlistEmail.trim()) {
                          waitlistMutation.mutate(waitlistEmail.trim())
                        }
                      }}
                      className="space-y-2"
                    >
                      <div className="flex gap-2">
                        <input
                          ref={emailInputRef}
                          type="email"
                          value={waitlistEmail}
                          onChange={(e) => setWaitlistEmail(e.target.value)}
                          placeholder="your@email.com"
                          className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                          required
                        />
                        <button
                          type="submit"
                          disabled={!waitlistEmail.trim() || waitlistMutation.isPending}
                          className={clsx(
                            'px-3 py-2 rounded-lg transition-colors flex items-center gap-1',
                            waitlistEmail.trim() && !waitlistMutation.isPending
                              ? 'bg-brand-600 text-white hover:bg-brand-700'
                              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                          )}
                        >
                          {waitlistMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Mail className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                      <p className="text-xs text-gray-500">
                        Only 20 spots available for early access!
                      </p>
                    </form>
                  </div>
                </div>
              )}

              {/* Waitlist success */}
              {waitlistSubmitted && (
                <div className="flex gap-2 justify-start">
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-green-100 flex items-center justify-center">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  </div>
                  <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-green-50 border border-green-200 px-4 py-3">
                    <p className="text-sm text-green-800 font-medium mb-1">
                      You're on the list! 🎉
                    </p>
                    <p className="text-sm text-green-700">
                      We'll reach out soon to get you started. Check your inbox!
                    </p>
                  </div>
                </div>
              )}

              {waitlistMutation.isError && (
                <div className="text-center py-2">
                  <p className="text-red-500 text-sm">
                    Oops! Something went wrong. Please try again.
                  </p>
                </div>
              )}
            </>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input - hide when waitlist is shown */}
        {!showWaitlist && (
          <form onSubmit={handleSubmit} className="p-3 border-t bg-white">
            <div className="flex gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask me anything about your semester..."
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
          </form>
        )}
      </div>
    </>
  )
}
