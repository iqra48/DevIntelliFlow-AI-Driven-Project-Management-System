import { Timestamp } from "firebase/firestore";


export interface Project {
  id: string;
  name: string;
  description: string;
  priority: "Low" | "Medium" | "High" | "Urgent"; 
  status: "Not Started" | "In Progress" | "Completed" | "On Hold";
  createdAt?: Timestamp | null;        
  lastOpenedAt?: Timestamp | null; 
  startDate?: string;
  timeEstimate?: number | null; // days between start & due   
  dueDate?: string;
  ownerId: string;          // project ka owner UID
  ownerEmail: string;       // project ka owner email  
  shareLinkEnabled?: boolean;
}
