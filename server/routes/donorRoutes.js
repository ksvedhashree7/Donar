import { Router } from 'express';
import { registerDonor } from '../controllers/donorController.js';

const router = Router();

router.post('/register', registerDonor);

export default router;
