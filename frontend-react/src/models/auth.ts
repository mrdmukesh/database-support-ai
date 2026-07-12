export interface Organization {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
}

export interface OrganizationCreate {
  name: string;
  slug: string;
}

export interface User {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface SignupRequest {
  organization_id: string;
  email: string;
  password: string;
  full_name?: string;
  role?: string;
  consents: string[];
  ip_address: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface Session {
  access_token: string;
  token_type: string;
  user: User;
}
