import {z} from'zod';
export const Risk=z.enum(['read','write','external','sensitive']);
export const Job=z.object({id:z.string(),kind:z.string(),status:z.enum(['queued','running','completed','failed']),progress:z.number().min(0).max(100),payload:z.record(z.string(),z.unknown()),result:z.record(z.string(),z.unknown()).nullable().optional(),created_at:z.string()});
export const UIComponent=z.object({type:z.enum(['Chat','QuickActions','ApprovalCard','SourceList','FileGrid','SyllabusTree','PlanTimeline','ProgressChart','ToolRun','PDFViewer']),data_ref:z.string().nullable().optional(),props:z.record(z.string(),z.unknown()).default({})});
export const UIManifest=z.object({version:z.literal(1),layout:z.enum(['chat','approval','study','research','files']),components:z.array(UIComponent)});
export const SyncMutation=z.object({id:z.string(),entity:z.enum(['topic_progress','task']),operation:z.enum(['upsert','delete']),payload:z.record(z.string(),z.unknown()),client_time:z.string()});
export type Job= z.infer<typeof Job>;export type UIManifest=z.infer<typeof UIManifest>;export type SyncMutation=z.infer<typeof SyncMutation>;
