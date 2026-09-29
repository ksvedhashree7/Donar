import { Router } from 'express';
import {
  approveBloodRequest,
  createBloodRequest,
  listPendingRequests,
  rejectBloodRequest,
} from '../controllers/requestController.js';

const router = Router();
const developmentAdminKey = process.env.NODE_ENV === 'production' ? '' : 'demo-admin';

function requireAdmin(request, response, next) {
  const expectedKey = process.env.ADMIN_API_KEY || developmentAdminKey;
  if (!expectedKey) {
    return response.status(503).json({ success: false, message: 'Admin verification is not configured.' });
  }
  if (request.get('x-admin-key') !== expectedKey) {
    return response.status(401).json({ success: false, message: 'A valid admin key is required.' });
  }
  return next();
}

router.post('/', createBloodRequest);
router.get('/pending', requireAdmin, listPendingRequests);
router.put('/:id/approve', requireAdmin, approveBloodRequest);
router.put('/:id/reject', requireAdmin, rejectBloodRequest);

export default router;