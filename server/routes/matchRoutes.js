import { Router } from 'express';
import { findMatches } from '../controllers/matchController.js';

const router = Router();

router.post('/', findMatches);

export default router;
