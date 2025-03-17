import numpy as np

def blackmanharris(N):
    """
    Return a Blackman-Harris window for scipy.
    
    This function is provided for compatibility with newer versions of scipy
    where blackmanharris has been moved to scipy.signal.windows.
    
    Parameters
    ----------
    N : int
        Number of points in the output window
        
    Returns
    -------
    w : ndarray
        The window
    """
    # Blackman-Harris window coefficients
    a0 = 0.35875
    a1 = 0.48829
    a2 = 0.14128
    a3 = 0.01168
    
    n = np.arange(N)
    w = (a0 
         - a1 * np.cos(2.0 * np.pi * n / (N-1)) 
         + a2 * np.cos(4.0 * np.pi * n / (N-1)) 
         - a3 * np.cos(6.0 * np.pi * n / (N-1)))
    
    return w 