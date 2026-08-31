import asyncio
import logging
import random
from datetime import datetime, timedelta
from app.services.enrichment_service import enrichment_service

logger = logging.getLogger(__name__)

class DiscoveryAgent:
    def __init__(self):
        self.trending_cities = [
            # --- DELHI ---
            "Chandni Chowk, Delhi", "India Gate, Delhi", "Red Fort, Delhi", "Akshardham Temple, Delhi", 
            "Qutub Minar, Delhi", "Connaught Place, Delhi", "Lotus Temple, Delhi", "Humayun's Tomb, Delhi", 
            "Hauz Khas Village, Delhi", "Lajpat Nagar, Delhi", "Sarojini Nagar, Delhi", "Khan Market, Delhi", 
            "Dilli Haat, Delhi", "Sundar Nursery, Delhi", "Majnu ka Tilla, Delhi", "Lodhi Garden, Delhi", 
            "Waste to Wonder Park, Delhi", "Garden of Five Senses, Delhi", "National Rail Museum, Delhi", 
            "Shankar's International Dolls Museum, Delhi", "Nehru Planetarium, Delhi", "National Museum, Delhi", 
            "Rashtrapati Bhavan, Delhi", "Jantar Mantar, Delhi", "Raj Ghat, Delhi", "Shanti Vana, Delhi", 
            "Vijay Ghat, Delhi", "Deer Park, Delhi", "Okhla Bird Sanctuary, Delhi", "Yamuna Biodiversity Park, Delhi",
            "Chhatarpur Temple, Delhi", "Safdarjung's Tomb, Delhi", "Purana Qila, Delhi", "National Zoological Park, Delhi",
            "Iskcon Temple, Delhi", "Agrasen ki Baoli, Delhi", "Mehrauli Archaeological Park, Delhi", 
            "Siri Fort, Delhi", "Tughlaqabad Fort, Delhi", "Nizamuddin Dargah, Delhi", "Bangla Sahib Gurudwara, Delhi",
            "Birla Mandir, Delhi", "Gurudwara Rakab Ganj, Delhi", "Sacred Heart Cathedral, Delhi", "St. James' Church, Delhi",
            "Majnu ka Tilla Monastery, Delhi", "Jama Masjid, Delhi", "Karol Bagh, Delhi", "Paharganj, Delhi", "Civil Lines, Delhi",
            "Netaji Subhash Place, Delhi", "Hudson Lane, Delhi", "Satya Niketan, Delhi", "North Campus, Delhi", "South Campus, Delhi",
            "Shahpur Jat, Delhi", "Greater Kailash, Delhi", "Defence Colony, Delhi", "South Extension, Delhi", "Vasant Kunj, Delhi",
            "Dwarka, Delhi", "Janakpuri, Delhi", "Rohini, Delhi", "Pitampura, Delhi", "Saket, Delhi",

            # --- NOIDA / GREATER NOIDA ---
            "DLF Mall of India, Noida", "Gardens Galleria, Noida", "Worlds of Wonder, Noida", "Okhla Bird Sanctuary, Noida", 
            "Botanic Garden, Noida", "Brahmaputra Market, Noida", "Sector 18, Noida", "Kidzania, Noida", 
            "ISKCON Temple, Noida", "Stupa 18 Art Gallery, Noida", "Snow World, Noida", "Grand Venice Mall, Greater Noida",
            "Surajpur Bird Sanctuary, Greater Noida", "Buddh International Circuit, Greater Noida", "Stellar Children's Museum, Greater Noida",
            "Vidhanchand Market, Noida", "Hazipur Sector 104, Noida", "Logix City Center, Noida", "Advant Navis, Noida",

            # --- GURGAON (GURUGRAM) ---
            "Cyber Hub, Gurgaon", "Kingdom of Dreams, Gurgaon", "Sultanpur Bird Sanctuary, Gurgaon", "Damdama Lake, Gurgaon", 
            "Leisure Valley Park, Gurgaon", "Sector 29, Gurgaon", "Ambience Mall, Gurgaon", "Museum of Folk and Tribal Art, Gurgaon", 
            "Heritage Transport Museum, Gurgaon", "Aravali Biodiversity Park, Gurgaon", "Tau Devi Lal Bio Diversity Park, Gurgaon", 
            "Sohna Hot Springs, Sohna", "Farrukhnagar Fort, Gurgaon", "NeverEnuf Garden Railway, Gurgaon", "Appu Ghar, Gurgaon",
            "Galleria Market, Gurgaon", "Star Mall, Gurgaon", "AIPL Joy Street, Gurgaon", "Badshahpur, Gurgaon", "Vatika City, Gurgaon",

            # --- FARIDABAD ---
            "Surajkund, Faridabad", "Badkhal Lake, Faridabad", "Nahar Singh Mahal, Faridabad", "CITM Lake, Faridabad", 
            "Raja Nahar Singh Palace, Faridabad", "Dhauj Lake, Faridabad", "Aravali Golf Course, Faridabad",
            "Death Valley, Faridabad", "Parson Temple, Faridabad", "Shirdi Sai Baba Temple, Faridabad", "Anangpur Dam, Faridabad",

            # --- GHAZIABAD ---
            "Indirapuram Habitat Centre, Ghaziabad", "Swarna Jayanti Park, Ghaziabad", "ISKCON Temple, Ghaziabad", "City Forest, Ghaziabad",
            "Drizzling Land, Ghaziabad", "Shipra Mall, Ghaziabad", "Masuri, Ghaziabad",

            # --- OTHER NCR ---
            "Surajkund Lake, Faridabad", "Sohna Lake, Sohna", "Garhmukteshwar, Hapur", "Meerut Cantt, Meerut", "Augarhnath Temple, Meerut",
            "Hastinapur, Meerut", "Kuchesar Fort, Bulandshahr", "Murthal, Sonipat", "Tilyar Lake, Rohtak", "Bhindawas Wildlife Sanctuary, Jhajjar"
        ]
        self.is_running = False

    async def run_daily_discovery(self):
        """
        Background process that continuously discovers trending places 
        from YouTube and Reddit, running periodically.
        """
        self.is_running = True
        logger.info("Started Scheduled Discovery Agent")
        
        while self.is_running:
            # 1. SHUFFLE: Pick a random subset of 20 cities to discover today
            # This implements the "10-20 jobs per day" limit to avoid anti-ban
            today_selection = random.sample(self.trending_cities, min(20, len(self.trending_cities)))
            logger.info(f"Discovery Engine starting daily batch for {len(today_selection)} cities.")

            for city in today_selection:
                if not self.is_running: break
                try:
                    logger.info(f"[Discovery Engine] Scanning {city} for new trends...")
                    # Trigger enrichment (Discovery Engine uses the background logic)
                    await enrichment_service.run_enrichment_job(city)
                    
                    # 2. RATE LIMITING: Jitter between 10 and 20 minutes
                    # Strict anti-ban strategy: slow and steady
                    sleep_time = random.randint(600, 1200)
                    logger.info(f"[Discovery Engine] Done with {city}. Sleeping for {sleep_time} seconds (Anti-Ban Rate Limit)...")
                    await asyncio.sleep(sleep_time)
                except Exception as e:
                    logger.error(f"Discovery engine job failed for {city}: {e}")
            
            # 3. DAILY CYCLE: Once 20 cities are done, sleep until tomorrow
            logger.info("Discovery Engine completed daily batch. Sleeping for 24 hours to reset limits.")
            # Sleep for 24 hours minus the time already spent (simplified to just 24h for reliability)
            await asyncio.sleep(86400)
            
    def start(self):
        """Standard method to hook into FastAPI startup event."""
        if not self.is_running:
            asyncio.create_task(self.run_daily_discovery())

discovery_agent = DiscoveryAgent()
