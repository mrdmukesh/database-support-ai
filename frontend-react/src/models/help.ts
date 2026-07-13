export interface HelpResponse { answer: string; steps: string[]; related_pages: string[]; warnings: string[]; links: string[] }
export interface HelpArticle { id: string; category: string; question: string; keywords: string[]; route?: string; requiredRoles?: string[] }
export interface HelpMessage { id: string; role: "user" | "assistant"; text: string; response?: HelpResponse }
