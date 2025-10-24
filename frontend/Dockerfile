FROM node:18-alpine

WORKDIR /app

# Copie des fichiers package
COPY package*.json ./
RUN npm install

# Copie du code source
COPY . .

# Exposition du port
EXPOSE 3000

# Commande de démarrage (dev mode pour hot reload)
CMD ["npm", "start"]
