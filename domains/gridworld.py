import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


class GridWorld:
    """A class for making gridworlds"""

    DIR = {'N': (-1, 0), 'S': (1, 0), 'E': (0, 1), 'W': (0, -1),
           'NE': (-1, 1), 'NW': (-1, -1), 'SE': (1, 1), 'SW': (1, -1)}

    def __init__(self, image, target_x, target_y):
        self.image = image
        self.n_row = image.shape[0]
        self.n_col = image.shape[1]
        self.obstacles = np.where(self.image == 0)
        self.freespace = np.where(self.image != 0)
        self.target_x = target_x
        self.target_y = target_y
        self.n_states = self.n_row * self.n_col
        self.n_actions = len(self.DIR)

        self.G, self.W, self.P, self.R, self.state_map_row, self.state_map_col = self.set_vals()

    def get_state_index(self, row, col):
        return np.ravel_multi_index([row, col], (self.n_row, self.n_col), order='F')

    def set_vals(self):
        # Setup function to initialize all necessary

        p = {dir: np.zeros((self.n_states, self.n_states)) for dir in self.DIR}

        R = -1 * np.ones((self.n_states, self.n_actions))
        R[:, 4:self.n_actions] = R[:, 4:self.n_actions] * np.sqrt(2)
        target = self.get_state_index(self.target_x, self.target_y)
        R[target, :] = 0

        for row in range(self.n_row):
            for col in range(self.n_col):
                curr_state = self.get_state_index(row, col)
                for dir in self.DIR:
                    neighbor_row, neighbor_col = self.move(row, col, dir)
                    neighbor_state = self.get_state_index(neighbor_row, neighbor_col)
                    p[dir][curr_state, neighbor_state] += 1

        G = np.logical_or.reduce(tuple(p.values()))

        W = np.maximum.reduce(tuple(p[dir] * np.linalg.norm(np.array(vec)) for dir, vec in self.DIR.items()))

        non_obstacles = self.get_state_index(self.freespace[0], self.freespace[1])

        non_obstacles = np.sort(non_obstacles)
        for dir in self.DIR:
            p[dir] = np.expand_dims(p[dir][non_obstacles, :][:, non_obstacles], axis=2)

        G = G[non_obstacles, :][:, non_obstacles]
        W = W[non_obstacles, :][:, non_obstacles]
        R = R[non_obstacles, :]
        P = np.concatenate(tuple(p.values()), axis=2)

        state_map_col, state_map_row = np.meshgrid(
            np.arange(0, self.n_col), np.arange(0, self.n_row))
        state_map_row = state_map_row.flatten('F')[non_obstacles]
        state_map_col = state_map_col.flatten('F')[non_obstacles]

        return G, W, P, R, state_map_row, state_map_col

    def get_graph(self):
        # Returns graph
        G = self.G
        W = self.W[self.W != 0]
        return G, W

    def get_graph_inv(self):
        # Returns transpose of graph
        G = self.G.T
        W = self.W.T
        return G, W

    def val_2_image(self, val):
        # Zeros for obstacles, val for free space
        im = np.zeros((self.n_row, self.n_col))
        im[self.freespace[0], self.freespace[1]] = val
        return im

    def get_value_prior(self):
        # Returns value prior for gridworld
        s_map_col, s_map_row = np.meshgrid(
            np.arange(0, self.n_col), np.arange(0, self.n_row))
        im = np.sqrt(
            np.square(s_map_col - self.target_y) +
            np.square(s_map_row - self.target_x))
        return im

    def get_reward_prior(self):
        # Returns reward prior for gridworld
        im = -1 * np.ones((self.n_row, self.n_col))
        im[self.target_x, self.target_y] = 10
        return im

    def t_get_reward_prior(self):
        # Returns reward prior as needed for
        #  dataset generation
        im = np.zeros((self.n_row, self.n_col))
        im[self.target_x, self.target_y] = 10
        return im

    def get_state_image(self, row, col):
        # Zeros everywhere except [row,col]
        im = np.zeros((self.n_row, self.n_col))
        im[row, col] = 1
        return im

    def map_ind_to_state(self, row, col):
        # Takes [row, col] and maps to a state
        rw = np.where(self.state_map_row == row)
        cl = np.where(self.state_map_col == col)
        return np.intersect1d(rw, cl)[0]

    def get_coords(self, states):
        # Given a state or states, returns
        #  [row,col] pairs for the state(s)
        non_obstacles = np.ravel_multi_index(
            [self.freespace[0], self.freespace[1]], (self.n_row, self.n_col),
            order='F')
        non_obstacles = np.sort(non_obstacles)
        states = states.astype(int)
        r, c = np.unravel_index(
            non_obstacles[states], (self.n_col, self.n_row), order='F')
        return r, c

    def rand_choose(self, in_vec):
        # Samples
        if len(in_vec.shape) > 1:
            if in_vec.shape[1] == 1:
                in_vec = in_vec.T
        temp = np.hstack((np.zeros((1)), np.cumsum(in_vec))).astype('int')
        q = np.random.rand()
        x = np.where(q > temp[0:-1])
        y = np.where(q < temp[1:])
        return np.intersect1d(x, y)[0]

    def next_state_prob(self, s, a):
        # Gets next state probability for
        #  a given action (a)
        if hasattr(a, "__iter__"):
            p = np.squeeze(self.P[s, :, a])
        else:
            p = np.squeeze(self.P[s, :, a]).T
        return p

    def sample_next_state(self, s, a):
        # Gets the next state given the
        #  current state (s) and an
        #  action (a)
        vec = self.next_state_prob(s, a)
        result = self.rand_choose(vec)
        return result

    def get_size(self):
        # Returns domain size
        return self.n_row, self.n_col

    def move(self, row, col, dir):
        # Returns new [row,col]
        #  if we take the action
        r_move, c_move = self.DIR[dir]
        new_row = max(0, min(row + r_move, self.n_row - 1))
        new_col = max(0, min(col + c_move, self.n_col - 1))
        if self.image[new_row, new_col] == 0:
            new_row = row
            new_col = col
        return new_row, new_col


def trace_path(pred, source, target):
    # traces back shortest path from
    #  source to target given pred
    #  (a predicessor list)
    max_len = 1000
    path = np.zeros((max_len, 1))
    i = max_len - 1
    path[i] = target
    while path[i] != source and i > 0:
        try:
            path[i - 1] = pred[int(path[i])]
            i -= 1
        except Exception as e:
            return []
    if i >= 0:
        path = path[i:]
    else:
        path = None
    return path


def sample_trajectory(M: GridWorld, n_states):
    # Samples trajectories from random nodes
    #  in our domain (M)
    G, W = M.get_graph_inv()
    N = G.shape[0]
    if N >= n_states:
        rand_ind = np.random.permutation(N)
    else:
        rand_ind = np.tile(np.random.permutation(N), (1, 10))
    init_states = rand_ind[0:n_states].flatten()
    goal_s = M.map_ind_to_state(M.target_x, M.target_y)
    states = []
    states_xy = []
    states_one_hot = []
    # Get optimal path from graph
    g_dense = W
    g_masked = np.ma.masked_values(g_dense, 0)
    g_sparse = csr_matrix(g_dense)
    d, pred = dijkstra(g_sparse, indices=goal_s, return_predecessors=True)
    for i in range(n_states):
        path = trace_path(pred, goal_s, init_states[i])
        path = np.flip(path, 0)
        states.append(path)
    for state in states:
        L = len(state)
        r, c = M.get_coords(state)
        row_m = np.zeros((L, M.n_row))
        col_m = np.zeros((L, M.n_col))
        for i in range(L):
            row_m[i, r[i]] = 1
            col_m[i, c[i]] = 1
        states_one_hot.append(np.hstack((row_m, col_m)))
        states_xy.append(np.hstack((r, c)))
    return states_xy, states_one_hot
