export interface PageResult<T> { items: T[]; page: number; page_size: number; total: number }
export interface Feedback { id:number; feedback_no:string; title:string; feedback_type:string; urgency:string; status:string; submitter_id:number; main_requirement_id?:number|null; revision:number }
export interface Requirement { id:number; requirement_no:string; title:string; requirement_type:string; source:string; priority:string; status:string; owner_id?:number|null; current_version_id?:number|null; description:string; acceptance_criteria?:string|null; revision:number }
export interface VersionItem { id:number; version_no:string; name:string; status:string; owner_id?:number|null; planned_release_date?:string|null; released_at?:string|null; revision:number }
export interface NotificationItem { id:number; title:string; content:string; entity_type?:string|null; entity_id?:number|null; read_at?:string|null; created_at:string }
